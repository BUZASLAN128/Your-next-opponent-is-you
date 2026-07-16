from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_DECLARATIONS
from ynoy.errors import DataValidationError
from ynoy.interaction_review import build_interaction_review
from ynoy.models.correction import (
    ClaimReviewDecision,
    ClaimReviewDecisionBase,
    InteractionCorrectionReceipt,
    MarkTemporaryClaimDecision,
    NarrowScopeClaimDecision,
    ProposeForCoreDecision,
    SplitClaimDecision,
)
from ynoy.models.interaction import AtomicClaimProposal, InteractionReview, SourceSpan
from ynoy.models.review_vocab import TargetLayer
from ynoy.util import canonical_sha256, new_id, utc_now

_DECISION_ADAPTER: TypeAdapter[ClaimReviewDecision] = TypeAdapter(ClaimReviewDecision)


def interaction_review_sha256(review: InteractionReview) -> str:
    """Return the canonical digest of a fully revalidated interaction review."""
    safe_review = _revalidate_review(review)
    return canonical_sha256(safe_review.model_dump(mode="json"))


def build_correction_receipt(
    review: InteractionReview,
    decisions: Sequence[ClaimReviewDecision],
    *,
    previous_receipt: InteractionCorrectionReceipt | None = None,
    record_id: UUID | None = None,
    created_at: datetime | None = None,
) -> InteractionCorrectionReceipt:
    """Build one explicit user correction receipt without persistence or provider use."""
    safe_review = _revalidate_review(review)
    receipt_time = created_at or utc_now()
    safe_decisions = validate_correction_decisions(safe_review, decisions, receipt_time)
    review_hash = canonical_sha256(safe_review.model_dump(mode="json"))
    previous = _revalidate_predecessor(previous_receipt, safe_review, review_hash)
    receipt_id = record_id or new_id()
    _validate_successor(previous, receipt_id, receipt_time)
    draft = InteractionCorrectionReceipt.model_construct(
        record_id=receipt_id,
        created_at=receipt_time,
        review_sha256=review_hash,
        previous_receipt_sha256=previous.receipt_sha256 if previous else None,
        sequence=(previous.sequence + 1) if previous else 1,
        subject_id=safe_review.subject_id,
        correction_data_class=safe_review.review_data_class,
        synthetic=safe_review.source.synthetic,
        decisions=safe_decisions,
        decision_count=len(safe_decisions),
        receipt_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"receipt_sha256"})
    complete = draft.model_dump(mode="python")
    complete["receipt_sha256"] = canonical_sha256(payload)
    return InteractionCorrectionReceipt.model_validate(complete)


def validate_correction_decisions(
    review: InteractionReview,
    decisions: Sequence[ClaimReviewDecision],
    receipt_time: datetime,
) -> tuple[ClaimReviewDecision, ...]:
    """Revalidate action semantics against the immutable source review."""
    safe_review = _revalidate_review(review)
    safe_decisions = tuple(_revalidate_decision(item) for item in decisions)
    if not safe_decisions:
        raise DataValidationError(
            "correction_decisions_required", "A correction receipt requires at least one decision."
        )
    if len(safe_decisions) > DEFAULT_BOOTSTRAP_MAX_DECLARATIONS:
        raise DataValidationError(
            "correction_decision_limit", "A correction receipt contains too many decisions."
        )
    if receipt_time.utcoffset() is None:
        raise DataValidationError(
            "correction_time_invalid", "Correction receipt time must be timezone-aware."
        )
    _validate_decisions(safe_review, safe_decisions, receipt_time)
    return safe_decisions


def _revalidate_review(review: InteractionReview) -> InteractionReview:
    if not isinstance(review, InteractionReview):
        raise DataValidationError(
            "interaction_review_required", "Correction requires a typed interaction review."
        )
    try:
        return InteractionReview.model_validate(review.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "interaction_review_invalid", "Interaction review failed correction validation."
        ) from exc


def _revalidate_decision(decision: ClaimReviewDecision) -> ClaimReviewDecision:
    if not isinstance(decision, ClaimReviewDecisionBase):
        raise DataValidationError(
            "correction_decision_required", "Correction accepts typed claim decisions only."
        )
    try:
        return _DECISION_ADAPTER.validate_python(decision.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "correction_decision_invalid", "Claim correction decision failed validation."
        ) from exc


def _revalidate_predecessor(
    receipt: InteractionCorrectionReceipt | None,
    review: InteractionReview,
    review_hash: str,
) -> InteractionCorrectionReceipt | None:
    if receipt is None:
        return None
    if not isinstance(receipt, InteractionCorrectionReceipt):
        raise DataValidationError(
            "correction_predecessor_required", "Correction predecessor must be a typed receipt."
        )
    try:
        safe = InteractionCorrectionReceipt.model_validate(receipt.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "correction_predecessor_invalid", "Correction predecessor failed validation."
        ) from exc
    if (
        safe.review_sha256 != review_hash
        or safe.subject_id != review.subject_id
        or safe.correction_data_class != review.review_data_class
        or safe.synthetic != review.source.synthetic
    ):
        raise DataValidationError(
            "correction_predecessor_mismatch", "Correction predecessor belongs to another review."
        )
    validate_correction_decisions(review, safe.decisions, safe.created_at)
    return safe


def _validate_successor(
    previous: InteractionCorrectionReceipt | None,
    record_id: UUID,
    created_at: datetime,
) -> None:
    if previous is None:
        return
    if record_id == previous.record_id:
        raise DataValidationError(
            "correction_receipt_duplicate", "Correction receipt requires a new identifier."
        )
    if created_at < previous.created_at:
        raise DataValidationError(
            "correction_time_order", "Correction receipt cannot predate its predecessor."
        )


def _validate_decisions(
    review: InteractionReview,
    decisions: tuple[ClaimReviewDecision, ...],
    receipt_time: datetime,
) -> None:
    claims = {item.record_id: item for item in review.claims}
    if len({item.claim_id for item in decisions}) != len(decisions):
        raise DataValidationError(
            "correction_claim_duplicate", "One receipt cannot decide one claim twice."
        )
    replacement_ids = [
        replacement.record_id
        for decision in decisions
        if isinstance(decision, SplitClaimDecision)
        for replacement in decision.replacements
    ]
    if len(replacement_ids) != len(set(replacement_ids)):
        raise DataValidationError(
            "correction_split_identifier_reused",
            "Split replacement identifiers must be unique across the receipt.",
        )
    for decision in decisions:
        claim = claims.get(decision.claim_id)
        if claim is None:
            raise DataValidationError(
                "correction_claim_unknown", "Correction decision targets an unknown claim."
            )
        if decision.subject_id != review.subject_id:
            raise DataValidationError(
                "correction_subject_mismatch", "Correction decision belongs to another subject."
            )
        _validate_action(review, claim, decision, receipt_time)


def _validate_action(
    review: InteractionReview,
    claim: AtomicClaimProposal,
    decision: ClaimReviewDecision,
    receipt_time: datetime,
) -> None:
    if isinstance(decision, SplitClaimDecision):
        _validate_split(review, claim, decision)
    elif isinstance(decision, NarrowScopeClaimDecision):
        if not _strictly_narrows(claim, decision):
            raise DataValidationError(
                "correction_scope_not_narrower", "Replacement scope must be strictly narrower."
            )
    elif isinstance(decision, MarkTemporaryClaimDecision):
        _validate_temporary(claim, decision, receipt_time)
    elif isinstance(decision, ProposeForCoreDecision):
        if claim.target_layer != TargetLayer.PERSONA_CANDIDATE:
            raise DataValidationError(
                "correction_core_target_invalid", "Core review can target persona candidates only."
            )


def _validate_split(
    review: InteractionReview,
    original: AtomicClaimProposal,
    decision: SplitClaimDecision,
) -> None:
    replacements = decision.replacements
    build_interaction_review(review.source, replacements)
    occupied = {item.record_id for item in review.claims}
    if any(item.record_id in occupied for item in replacements):
        raise DataValidationError(
            "correction_split_identifier_reused", "Split replacements require new identifiers."
        )
    for replacement in replacements:
        if not all(_span_is_within(span, original) for span in replacement.source_spans):
            raise DataValidationError(
                "correction_split_span_invalid",
                "Split replacement spans must remain inside the original claim evidence.",
            )


def _span_is_within(span: SourceSpan, original: AtomicClaimProposal) -> bool:
    start = span.character_start
    end = span.character_end
    return any(
        source.character_start <= start and end <= source.character_end
        for source in original.source_spans
    )


def _strictly_narrows(claim: AtomicClaimProposal, decision: NarrowScopeClaimDecision) -> bool:
    original = claim.scope
    replacement = decision.replacement_scope
    if replacement.person_id != original.person_id:
        return False
    if (
        replacement.valid_from != original.valid_from
        or replacement.valid_until != original.valid_until
    ):
        return False
    changed = False
    for field in ("project", "role", "audience"):
        old, new = getattr(original, field), getattr(replacement, field)
        if old is not None and new != old:
            return False
        changed |= old is None and new is not None
    if original.risk != "unknown" and replacement.risk != original.risk:
        return False
    changed |= original.risk == "unknown" and replacement.risk != "unknown"
    return changed


def _validate_temporary(
    claim: AtomicClaimProposal,
    decision: MarkTemporaryClaimDecision,
    receipt_time: datetime,
) -> None:
    if decision.valid_until <= receipt_time:
        raise DataValidationError(
            "correction_temporary_invalid", "Temporary validity must end after the correction."
        )
    current_end = claim.scope.valid_until
    if current_end is not None and decision.valid_until >= current_end:
        raise DataValidationError(
            "correction_temporary_not_narrower",
            "Temporary correction cannot extend existing validity.",
        )
    if claim.scope.valid_from is not None and decision.valid_until < claim.scope.valid_from:
        raise DataValidationError(
            "correction_temporary_interval_invalid",
            "Temporary validity cannot end before the claim begins.",
        )
