from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid5

from ynoy.correction import interaction_review_sha256
from ynoy.errors import DataValidationError
from ynoy.models.base import ScopeRef
from ynoy.models.correction import (
    ClaimReviewDecision,
    ConfirmClaimDecision,
    InteractionCorrectionReceipt,
    MakeProjectRuleDecision,
    MarkTemporaryClaimDecision,
    NarrowScopeClaimDecision,
    ProposeForCoreDecision,
    RejectClaimDecision,
    RejectInferenceDecision,
    SplitClaimDecision,
)
from ynoy.models.interaction import (
    AtomicClaimProposal,
    InteractionReview,
    NullableReviewText,
)
from ynoy.models.review_state import (
    ClaimReviewEvent,
    DeletionDependencyProjection,
    ReviewedClaimState,
    ReviewedInteractionState,
)
from ynoy.models.review_vocab import NullReason, ReviewOutcome
from ynoy.review_chain import revalidate_interaction_review, validate_correction_chain
from ynoy.util import canonical_sha256

_DERIVED_NAMESPACE = UUID("fbb32de4-997a-54b3-b30c-463d4628d86f")


def replay_interaction_review(
    review: InteractionReview,
    correction_receipts: Sequence[InteractionCorrectionReceipt],
) -> ReviewedInteractionState:
    """Replay a supplied correction chain without sorting, persistence, or fallback."""
    safe_review = revalidate_interaction_review(review)
    review_hash = interaction_review_sha256(safe_review)
    receipts = validate_correction_chain(safe_review, review_hash, correction_receipts)
    states = {
        claim.record_id: ReviewedClaimState(
            original=claim,
            effective_claims=(),
            outcome=ReviewOutcome.PENDING,
            active=False,
            history=(),
        )
        for claim in safe_review.claims
    }
    for receipt in receipts:
        for decision in receipt.decisions:
            current = states[decision.claim_id]
            states[decision.claim_id] = _apply_decision(current, decision, receipt)
    ordered = tuple(states[claim.record_id] for claim in safe_review.claims)
    return _build_state(safe_review, review_hash, receipts, ordered)


def review_deletion_dependencies(
    review: InteractionReview,
    correction_receipts: Sequence[InteractionCorrectionReceipt],
) -> DeletionDependencyProjection:
    """Project the complete in-memory dependency closure without deleting anything."""
    state = replay_interaction_review(review, correction_receipts)
    claim_ids = {item.original.record_id for item in state.claims} | {
        claim_id
        for item in state.claims
        for event in item.history
        for claim_id in event.effective_claim_ids
    }
    return DeletionDependencyProjection(
        source_receipt_id=state.source_receipt_id,
        review_sha256=state.review_sha256,
        dependent_claim_ids=tuple(sorted(claim_ids, key=str)),
        dependent_correction_receipt_ids=state.correction_receipt_ids,
        dependent_correction_hashes=state.correction_receipt_hashes,
        total_dependency_count=1 + len(claim_ids) + len(state.correction_receipt_ids),
    )


def _apply_decision(
    current: ReviewedClaimState,
    decision: ClaimReviewDecision,
    receipt: InteractionCorrectionReceipt,
) -> ReviewedClaimState:
    effective, outcome = _effective_claims(current.original, decision, receipt)
    history = list(current.history)
    if history:
        history[-1] = history[-1].model_copy(
            update={"superseded_by_receipt_sha256": receipt.receipt_sha256}
        )
    history.append(
        ClaimReviewEvent(
            correction_receipt_id=receipt.record_id,
            correction_receipt_sha256=receipt.receipt_sha256,
            sequence=receipt.sequence,
            action=decision.action,
            outcome=outcome,
            effective_claim_ids=tuple(item.record_id for item in effective),
        )
    )
    return ReviewedClaimState(
        original=current.original,
        effective_claims=effective,
        outcome=outcome,
        active=outcome != ReviewOutcome.REJECTED,
        core_review_requested=outcome == ReviewOutcome.CORE_REVIEW_REQUESTED,
        history=tuple(history),
    )


def _effective_claims(
    original: AtomicClaimProposal,
    decision: ClaimReviewDecision,
    receipt: InteractionCorrectionReceipt,
) -> tuple[tuple[AtomicClaimProposal, ...], ReviewOutcome]:
    if isinstance(decision, ConfirmClaimDecision):
        return (original,), ReviewOutcome.CONFIRMED
    if isinstance(decision, RejectClaimDecision):
        return (), ReviewOutcome.REJECTED
    if isinstance(decision, SplitClaimDecision):
        return decision.replacements, ReviewOutcome.SPLIT
    if isinstance(decision, ProposeForCoreDecision):
        return (original,), ReviewOutcome.CORE_REVIEW_REQUESTED
    return (_revise_claim(original, decision, receipt),), ReviewOutcome.REVISED


def _revise_claim(
    original: AtomicClaimProposal,
    decision: ClaimReviewDecision,
    receipt: InteractionCorrectionReceipt,
) -> AtomicClaimProposal:
    updates: dict[str, object] = {
        "record_id": uuid5(
            _DERIVED_NAMESPACE,
            f"{receipt.receipt_sha256}:{original.record_id}:{decision.action.value}",
        ),
        "created_at": receipt.created_at,
    }
    if isinstance(decision, NarrowScopeClaimDecision):
        updates["scope"] = decision.replacement_scope
    elif isinstance(decision, MarkTemporaryClaimDecision):
        scope = original.scope.model_copy(update={"valid_until": decision.valid_until})
        updates["scope"] = ScopeRef.model_validate(scope.model_dump(mode="python"))
    elif isinstance(decision, MakeProjectRuleDecision):
        updates["target_layer"] = decision.target_layer
    elif isinstance(decision, RejectInferenceDecision):
        empty = NullableReviewText(
            null_reason=NullReason.NOT_APPLICABLE,
            authority_to_fill="evidence_required",
        )
        updates.update(inference=empty, candidate_consequence=empty)
    else:
        raise DataValidationError(
            "correction_action_unsupported", "Correction action has no replay transition."
        )
    return AtomicClaimProposal.model_validate(
        original.model_copy(update=updates).model_dump(mode="python")
    )


def _build_state(
    review: InteractionReview,
    review_hash: str,
    receipts: tuple[InteractionCorrectionReceipt, ...],
    claims: tuple[ReviewedClaimState, ...],
) -> ReviewedInteractionState:
    pending = tuple(
        item.original.record_id for item in claims if item.outcome == ReviewOutcome.PENDING
    )
    status = (
        "awaiting_user_confirmation"
        if not receipts
        else ("partially_reviewed" if pending else "reviewed")
    )
    draft = ReviewedInteractionState.model_construct(
        source_receipt_id=review.source.record_id,
        source_name=review.source.source_name,
        source_conversation_id=review.source.conversation_id,
        source_turn_id=review.source.turn_id,
        review_sha256=review_hash,
        subject_id=review.subject_id,
        data_class=review.review_data_class,
        correction_receipt_ids=tuple(item.record_id for item in receipts),
        correction_receipt_hashes=tuple(item.receipt_sha256 for item in receipts),
        receipt_head_sha256=receipts[-1].receipt_sha256 if receipts else None,
        claims=claims,
        review_status=status,
        pending_claim_ids=pending,
        state_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"state_sha256"})
    complete = draft.model_dump(mode="python")
    complete["state_sha256"] = canonical_sha256(payload)
    return ReviewedInteractionState.model_validate(complete)
