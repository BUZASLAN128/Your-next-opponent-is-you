from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ynoy.correction import build_correction_receipt
from ynoy.errors import DataValidationError
from ynoy.models import (
    ClaimReviewDecision,
    DeletionDependencyProjection,
    InteractionCorrectionReceipt,
    InteractionReview,
    ReviewedInteractionState,
)
from ynoy.review_replay import replay_interaction_review, review_deletion_dependencies


@dataclass(frozen=True, slots=True)
class AppliedReviewCorrection:
    receipt: InteractionCorrectionReceipt
    state: ReviewedInteractionState
    deletion: DeletionDependencyProjection


def apply_review_correction(
    review: InteractionReview,
    decisions: Sequence[ClaimReviewDecision],
    existing: Sequence[InteractionCorrectionReceipt],
) -> AppliedReviewCorrection:
    """Build and replay one correction while proving deterministic state."""
    if existing:
        replay_interaction_review(review, existing)
    receipt = build_correction_receipt(
        review,
        decisions,
        previous_receipt=existing[-1] if existing else None,
    )
    chain = (*existing, receipt)
    state = replay_interaction_review(review, chain)
    repeated = replay_interaction_review(review, chain)
    if repeated.state_sha256 != state.state_sha256:
        raise DataValidationError(
            "review_replay_nondeterministic", "Repeated correction replay changed state."
        )
    return AppliedReviewCorrection(
        receipt=receipt,
        state=state,
        deletion=review_deletion_dependencies(review, chain),
    )
