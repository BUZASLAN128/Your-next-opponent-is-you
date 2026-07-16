from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from ynoy.correction import validate_correction_decisions
from ynoy.errors import DataValidationError
from ynoy.models.correction import InteractionCorrectionReceipt, SplitClaimDecision
from ynoy.models.interaction import InteractionReview


def revalidate_interaction_review(review: InteractionReview) -> InteractionReview:
    """Return a fully validated typed review for deterministic replay."""
    if not isinstance(review, InteractionReview):
        raise DataValidationError(
            "interaction_review_required", "Replay requires a typed interaction review."
        )
    try:
        return InteractionReview.model_validate(review.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "interaction_review_invalid", "Interaction review failed replay validation."
        ) from exc


def validate_correction_chain(
    review: InteractionReview,
    review_hash: str,
    receipts: Sequence[InteractionCorrectionReceipt],
) -> tuple[InteractionCorrectionReceipt, ...]:
    """Validate supplied receipt order, boundaries, semantics, and identifiers."""
    safe_receipts: list[InteractionCorrectionReceipt] = []
    receipt_ids: set[UUID] = set()
    receipt_hashes: set[str] = set()
    previous_hash: str | None = None
    previous_time: datetime | None = None
    claim_ids = {item.record_id for item in review.claims}
    used_claim_ids = set(claim_ids)
    for expected_sequence, receipt in enumerate(receipts, start=1):
        safe = _revalidate_receipt(receipt)
        if safe.record_id in receipt_ids or safe.receipt_sha256 in receipt_hashes:
            raise DataValidationError(
                "correction_chain_duplicate", "Correction receipt chain contains a duplicate."
            )
        _validate_receipt_link(
            review, review_hash, claim_ids, safe, expected_sequence, previous_hash
        )
        if previous_time is not None and safe.created_at < previous_time:
            raise DataValidationError(
                "correction_chain_time", "Correction receipt chain is not chronological."
            )
        validate_correction_decisions(review, safe.decisions, safe.created_at)
        _register_split_claim_ids(safe, used_claim_ids)
        safe_receipts.append(safe)
        receipt_ids.add(safe.record_id)
        receipt_hashes.add(safe.receipt_sha256)
        previous_hash = safe.receipt_sha256
        previous_time = safe.created_at
    return tuple(safe_receipts)


def _revalidate_receipt(receipt: InteractionCorrectionReceipt) -> InteractionCorrectionReceipt:
    if not isinstance(receipt, InteractionCorrectionReceipt):
        raise DataValidationError(
            "correction_receipt_required", "Replay accepts typed correction receipts only."
        )
    try:
        return InteractionCorrectionReceipt.model_validate(receipt.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "correction_receipt_invalid", "Correction receipt failed replay validation."
        ) from exc


def _validate_receipt_link(
    review: InteractionReview,
    review_hash: str,
    claim_ids: set[UUID],
    receipt: InteractionCorrectionReceipt,
    expected_sequence: int,
    previous_hash: str | None,
) -> None:
    if receipt.sequence != expected_sequence:
        raise DataValidationError(
            "correction_chain_sequence", "Correction receipt sequence is missing or reordered."
        )
    if receipt.previous_receipt_sha256 != previous_hash:
        raise DataValidationError(
            "correction_chain_predecessor", "Correction receipt predecessor hash is invalid."
        )
    if receipt.review_sha256 != review_hash:
        raise DataValidationError(
            "correction_chain_review", "Correction receipt belongs to another review."
        )
    if (
        receipt.subject_id != review.subject_id
        or receipt.correction_data_class != review.review_data_class
        or receipt.synthetic != review.source.synthetic
    ):
        raise DataValidationError(
            "correction_chain_boundary", "Correction receipt crosses subject or data boundary."
        )
    if any(item.claim_id not in claim_ids for item in receipt.decisions):
        raise DataValidationError(
            "correction_chain_claim", "Correction receipt targets a claim outside the review."
        )


def _register_split_claim_ids(
    receipt: InteractionCorrectionReceipt,
    used_claim_ids: set[UUID],
) -> None:
    replacement_ids = {
        replacement.record_id
        for decision in receipt.decisions
        if isinstance(decision, SplitClaimDecision)
        for replacement in decision.replacements
    }
    if replacement_ids & used_claim_ids:
        raise DataValidationError(
            "correction_chain_claim_identifier",
            "Split replacement identifiers must be new across the receipt chain.",
        )
    used_claim_ids.update(replacement_ids)
