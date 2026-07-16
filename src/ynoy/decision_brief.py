from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models.base import ScopeRef
from ynoy.models.decision_brief import DecisionBrief, DecisionBriefEntry, DecisionConflict
from ynoy.models.interaction import AtomicClaimProposal
from ynoy.models.review_state import (
    ClaimReviewEvent,
    ReviewedClaimState,
    ReviewedInteractionState,
)
from ynoy.models.review_vocab import ClaimModality, ReviewOutcome, TargetLayer
from ynoy.scope import scope_is_active, scope_matches

_PROJECT_LAYERS = {TargetLayer.PROJECT_CONSTITUTION, TargetLayer.SCOPED_POLICY}
_RESEARCH_LAYERS = {
    TargetLayer.ARCHITECTURE_CANDIDATE,
    TargetLayer.EXPERIMENT_BACKLOG,
    TargetLayer.RESEARCH_VISION,
}
_POSITIVE_MODALITIES = {
    ClaimModality.MUST,
    ClaimModality.SHOULD,
    ClaimModality.PREFER,
}


def resolve_decision_brief(
    reviewed_state: ReviewedInteractionState,
    requested_scope: ScopeRef,
    evaluation_time: datetime,
) -> DecisionBrief:
    """Resolve a scoped brief without semantic guessing, persistence, or model calls."""
    state = _revalidate_state(reviewed_state)
    scope = _revalidate_scope(requested_scope)
    if scope.person_id != state.subject_id:
        raise DataValidationError(
            "decision_brief_subject_mismatch", "Requested scope belongs to another subject."
        )
    if evaluation_time.utcoffset() is None:
        raise DataValidationError(
            "decision_brief_time_invalid", "Decision brief time must be timezone-aware."
        )
    entries = tuple(_applicable_entries(state, scope, evaluation_time))
    pending = _applicable_pending(state, scope, evaluation_time)
    conflicts = _find_conflicts(entries)
    groups = _partition(entries)
    unknowns = _unknowns(entries, pending, conflicts)
    abstention_reasons = _abstention_reasons(entries, conflicts)
    return DecisionBrief(
        subject_id=state.subject_id,
        data_class=state.data_class,
        source_name=state.source_name,
        source_conversation_id=state.source_conversation_id,
        source_turn_id=state.source_turn_id,
        requested_scope=scope,
        evaluated_at=evaluation_time,
        protected_controls=groups["protected"],
        project_rules=groups["project"],
        active_missions=groups["mission"],
        episodic_context=groups["episodic"],
        persona_candidates=groups["persona"],
        research_candidates=groups["research"],
        conflicts=conflicts,
        pending_claim_ids=pending,
        unknowns=unknowns,
        abstention_reasons=abstention_reasons,
        used_source_receipt_ids=(state.source_receipt_id,),
        used_correction_receipt_ids=state.correction_receipt_ids,
        used_correction_receipt_hashes=state.correction_receipt_hashes,
        abstained=bool(abstention_reasons),
    )


def _revalidate_state(state: ReviewedInteractionState) -> ReviewedInteractionState:
    if not isinstance(state, ReviewedInteractionState):
        raise DataValidationError(
            "reviewed_state_required", "Decision brief requires a typed reviewed state."
        )
    try:
        return ReviewedInteractionState.model_validate(state.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "reviewed_state_invalid", "Reviewed state failed decision brief validation."
        ) from exc


def _revalidate_scope(scope: ScopeRef) -> ScopeRef:
    if not isinstance(scope, ScopeRef):
        raise DataValidationError(
            "decision_brief_scope_required", "Decision brief requires a typed scope."
        )
    try:
        return ScopeRef.model_validate(scope.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "decision_brief_scope_invalid", "Decision brief scope failed validation."
        ) from exc


def _applicable_entries(
    state: ReviewedInteractionState,
    scope: ScopeRef,
    evaluated_at: datetime,
) -> list[DecisionBriefEntry]:
    entries: list[DecisionBriefEntry] = []
    for claim_state in state.claims:
        if not claim_state.active or not claim_state.history:
            continue
        event = claim_state.history[-1]
        for claim in claim_state.effective_claims:
            if not scope_matches(claim.scope, scope) or not scope_is_active(
                claim.scope, evaluated_at
            ):
                continue
            entries.append(_entry(claim_state, claim, state, event))
    return entries


def _entry(
    state: ReviewedClaimState,
    claim: AtomicClaimProposal,
    reviewed: ReviewedInteractionState,
    event: ClaimReviewEvent,
) -> DecisionBriefEntry:
    return DecisionBriefEntry(
        claim_id=claim.record_id,
        source_claim_id=state.original.record_id,
        statement=claim.literal_normalization,
        modality=claim.modality,
        claim_type=claim.claim_type,
        target_layer=claim.target_layer,
        scope=claim.scope,
        review_outcome=state.outcome,
        review_action=event.action,
        source_receipt_id=reviewed.source_receipt_id,
        correction_receipt_id=event.correction_receipt_id,
        correction_receipt_sha256=event.correction_receipt_sha256,
    )


def _applicable_pending(
    state: ReviewedInteractionState,
    scope: ScopeRef,
    evaluated_at: datetime,
) -> tuple[UUID, ...]:
    return tuple(
        item.original.record_id
        for item in state.claims
        if item.outcome == ReviewOutcome.PENDING
        and scope_matches(item.original.scope, scope)
        and scope_is_active(item.original.scope, evaluated_at)
    )


def _partition(
    entries: tuple[DecisionBriefEntry, ...],
) -> dict[str, tuple[DecisionBriefEntry, ...]]:
    return {
        "protected": tuple(
            item for item in entries if item.target_layer == TargetLayer.PROTECTED_CONTROL
        ),
        "project": tuple(item for item in entries if item.target_layer in _PROJECT_LAYERS),
        "mission": tuple(
            item for item in entries if item.target_layer == TargetLayer.MISSION_STATE
        ),
        "episodic": tuple(
            item for item in entries if item.target_layer == TargetLayer.EPISODIC_MEMORY
        ),
        "persona": tuple(
            item for item in entries if item.target_layer == TargetLayer.PERSONA_CANDIDATE
        ),
        "research": tuple(item for item in entries if item.target_layer in _RESEARCH_LAYERS),
    }


def _find_conflicts(entries: tuple[DecisionBriefEntry, ...]) -> tuple[DecisionConflict, ...]:
    groups: dict[tuple[str, str], list[DecisionBriefEntry]] = defaultdict(list)
    for item in entries:
        key = (
            item.target_layer.value,
            " ".join(item.statement.casefold().split()),
        )
        groups[key].append(item)
    conflicts = []
    for values in groups.values():
        modalities = {item.modality for item in values}
        if ClaimModality.MUST_NOT in modalities and modalities & _POSITIVE_MODALITIES:
            conflicts.append(
                DecisionConflict(
                    target_layer=values[0].target_layer,
                    claim_ids=tuple(sorted((item.claim_id for item in values), key=str)),
                )
            )
    return tuple(sorted(conflicts, key=lambda item: tuple(map(str, item.claim_ids))))


def _unknowns(
    entries: tuple[DecisionBriefEntry, ...],
    pending: tuple[UUID, ...],
    conflicts: tuple[DecisionConflict, ...],
) -> tuple[str, ...]:
    values = ["semantic_conflict_detection_limited_to_exact_normalization"]
    if not entries:
        values.append("no_applicable_reviewed_decisions")
    if pending:
        values.append("pending_review")
    if conflicts:
        values.append("unresolved_conflict")
    return tuple(values)


def _abstention_reasons(
    entries: tuple[DecisionBriefEntry, ...],
    conflicts: tuple[DecisionConflict, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not entries:
        reasons.append("no_applicable_reviewed_decisions")
    if conflicts:
        reasons.append("unresolved_conflict")
    return tuple(reasons)
