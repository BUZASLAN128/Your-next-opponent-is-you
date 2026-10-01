from __future__ import annotations

from collections.abc import Mapping, Sequence

from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.errors import DataValidationError
from ynoy.models import ClaimReviewDecision, RejectClaimDecision
from ynoy.models.correction import ConfirmClaimDecision, SplitClaimDecision
from ynoy.models.review_state import ReviewedClaimState, ReviewedInteractionState
from ynoy.models.review_vocab import ReviewOutcome


def validate_operation(
    database: DirectMemoryDatabase,
    operation: str,
    decisions: Sequence[ClaimReviewDecision],
    project: str,
    facts: Sequence[Mapping[str, object]],
    supersessions: Mapping[str, str] | None,
) -> dict[str, str]:
    if operation == "supersede":
        raise DataValidationError(
            "direct_memory_supersession_binding_required",
            "Supersession requires a query-valid canonical claim binding that this adapter lacks.",
        )
    claim_to_fact = {str(item["claim_id"]): str(item["fact_key"]) for item in facts}
    selected = {claim_to_fact.get(str(item.claim_id)) for item in decisions}
    if not decisions or None in selected:
        raise DataValidationError(
            "direct_memory_fact_link_missing", "Correction targets require stable fact keys."
        )
    if operation not in {"correct", "retract", "supersede"}:
        raise DataValidationError(
            "direct_memory_correction_kind", "Correction operation is unknown."
        )
    if supersessions and operation != "supersede":
        raise DataValidationError(
            "direct_memory_supersession_invalid", "Only supersession may name replacement facts."
        )
    if operation == "retract" and any(
        not isinstance(item, RejectClaimDecision) for item in decisions
    ):
        raise DataValidationError(
            "direct_memory_retraction_invalid",
            "Retraction requires explicit native rejection decisions.",
        )
    return claim_to_fact


def validate_kind(operation: str) -> None:
    if operation not in {"correct", "retract", "supersede"}:
        raise DataValidationError(
            "direct_memory_correction_kind",
            "Correction operation must be correct, retract, or supersede.",
        )


def validate_correction_continuity(
    state: ReviewedInteractionState, decisions: Sequence[ClaimReviewDecision]
) -> None:
    current_by_id = {item.original.record_id: item for item in state.claims}
    for decision in decisions:
        current = current_by_id[decision.claim_id]
        if not current.history:
            continue
        changed = _effective_claim_changed(current)
        if not changed:
            continue
        if isinstance(decision, (RejectClaimDecision, SplitClaimDecision)):
            continue
        if current.outcome == ReviewOutcome.REJECTED and isinstance(decision, ConfirmClaimDecision):
            continue
        raise DataValidationError(
            "direct_memory_incremental_correction_unsafe",
            "A correction cannot silently restore fields from the original claim; "
            "provide complete replacement claims or explicitly confirm a rejected original.",
        )


def _effective_claim_changed(current: ReviewedClaimState) -> bool:
    if len(current.effective_claims) != 1:
        return True
    original = current.original.model_dump(mode="json", exclude={"record_id", "created_at"})
    effective = current.effective_claims[0].model_dump(
        mode="json", exclude={"record_id", "created_at"}
    )
    return original != effective


__all__ = ["validate_kind", "validate_operation"]
