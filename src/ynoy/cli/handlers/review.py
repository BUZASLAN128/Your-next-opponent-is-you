from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import require_matching_mode
from ynoy.correction import interaction_review_sha256
from ynoy.errors import AdapterError, DataValidationError
from ynoy.extractor import LocalAtomicExtractor
from ynoy.models import (
    AtomicClaimProposal,
    ClaimReviewDecision,
    InteractionCorrectionReceipt,
    InteractionReceipt,
    InteractionReview,
)
from ynoy.policy import assert_outside_git, require_private_source
from ynoy.review_application import apply_review_correction
from ynoy.review_files import load_review_decisions, load_review_model
from ynoy.review_replay import replay_interaction_review, review_deletion_dependencies


def handle_review(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    handlers = {
        "propose": _propose,
        "batch": _batch,
        "apply": _apply,
        "replay": _replay,
    }
    return handlers[args.review_command](args, context)


def _propose(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source = _authorized_path(args.interaction, context, synthetic=synthetic)
    receipt = load_review_model(source, InteractionReceipt, label="interaction_receipt")
    require_matching_mode(requested_synthetic=synthetic, artifact_synthetic=receipt.synthetic)
    store = context.review_artifacts(synthetic=synthetic)
    settings = context.settings
    required = (
        settings.local_reasoner_url,
        settings.local_reasoner_revision,
        settings.local_reasoner_artifact_sha256,
    )
    if not all(required):
        raise AdapterError(
            "local_extractor_not_configured",
            "Set the local endpoint, model revision, and model artifact SHA-256.",
        )
    extractor = LocalAtomicExtractor(
        endpoint=settings.local_reasoner_url or "",
        model=settings.local_reasoner_model,
        revision=settings.local_reasoner_revision or "",
        artifact_sha256=settings.local_reasoner_artifact_sha256 or "",
        local_attested=settings.local_model_attested,
    )
    review = extractor.propose(receipt)
    digest = interaction_review_sha256(review)
    path = store.write_model("interaction-reviews", digest, review)
    return {
        "status": "awaiting_user_confirmation",
        "review_sha256": digest,
        "review_path": str(path),
        "claim_count": review.claim_count,
        "proposal_method": review.proposal_method,
        "provider_used": review.provider_used,
        "database_used": review.database_used,
        "storage_protection": store.storage_protection,
        "automatic_core_promotion": review.automatic_core_promotion,
    }


def _batch(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    review = _load_review(args.review, context, synthetic=synthetic)
    start = int(args.start)
    limit = int(args.limit)
    if start < 1 or limit < 1 or limit > 20:
        raise DataValidationError(
            "review_batch_invalid", "Review batches require start >= 1 and 1 <= limit <= 20."
        )
    selected = review.claims[start - 1 : start - 1 + limit]
    return {
        "review_sha256": interaction_review_sha256(review),
        "claim_count": review.claim_count,
        "start": start,
        "returned": len(selected),
        "has_more": start - 1 + len(selected) < review.claim_count,
        "storage_protection": _review_storage_label(synthetic),
        "allowed_actions": [item.value for item in review.allowed_actions],
        "claims": [_claim_view(start + index, claim) for index, claim in enumerate(selected)],
    }


def _apply(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    review = _load_review(args.review, context, synthetic=synthetic)
    decisions = _load_decisions(args.decisions, context, synthetic=synthetic)
    existing = _load_receipts(
        args.receipt,
        context,
        review,
        synthetic=synthetic,
    )
    applied = apply_review_correction(review, decisions, existing)
    receipt, state, closure = applied.receipt, applied.state, applied.deletion
    store = context.review_artifacts(synthetic=synthetic)
    written: list[tuple[str, str]] = []
    try:
        receipt_path = store.write_model("correction-receipts", receipt.record_id, receipt)
        written.append(("correction-receipts", str(receipt.record_id)))
        state_path = store.write_model("reviewed-states", receipt.record_id, state)
        written.append(("reviewed-states", str(receipt.record_id)))
        closure_path = store.write_model("review-deletion-closures", receipt.record_id, closure)
    except Exception:
        for category, artifact_id in reversed(written):
            store.delete_if_exists(category, artifact_id)
        raise
    return {
        "status": state.review_status,
        "receipt_id": str(receipt.record_id),
        "receipt_sha256": receipt.receipt_sha256,
        "receipt_path": str(receipt_path),
        "state_sha256": state.state_sha256,
        "state_path": str(state_path),
        "deletion_closure_path": str(closure_path),
        "pending_count": len(state.pending_claim_ids),
        "replay_count": 2,
        "database_used": False,
        "provider_used": review.provider_used,
        "storage_protection": store.storage_protection,
        "automatic_core_promotion": False,
    }


def _replay(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    review = _load_review(args.review, context, synthetic=synthetic)
    receipts = _load_receipts(
        args.receipt,
        context,
        review,
        synthetic=synthetic,
    )
    state = replay_interaction_review(review, receipts)
    repeated = replay_interaction_review(review, receipts)
    closure = review_deletion_dependencies(review, receipts)
    return {
        "status": state.review_status,
        "state_sha256": state.state_sha256,
        "deterministic": state.state_sha256 == repeated.state_sha256,
        "receipt_count": len(receipts),
        "pending_count": len(state.pending_claim_ids),
        "dependency_count": closure.total_dependency_count,
        "deletion_performed": False,
        "storage_protection": _review_storage_label(synthetic),
    }


def _load_review(
    value: str,
    context: CommandContext,
    *,
    synthetic: bool,
) -> InteractionReview:
    path = _authorized_path(value, context, synthetic=synthetic)
    review = load_review_model(path, InteractionReview, label="interaction_review")
    require_matching_mode(requested_synthetic=synthetic, artifact_synthetic=review.source.synthetic)
    return review


def _load_receipts(
    values: list[str],
    context: CommandContext,
    review: InteractionReview,
    *,
    synthetic: bool,
) -> tuple[InteractionCorrectionReceipt, ...]:
    receipts = tuple(
        load_review_model(
            _authorized_path(value, context, synthetic=synthetic),
            InteractionCorrectionReceipt,
            label="correction_receipt",
        )
        for value in values
    )
    if any(item.synthetic != review.source.synthetic for item in receipts):
        raise DataValidationError(
            "correction_receipt_mode_mismatch", "Correction receipt crosses the data boundary."
        )
    return receipts


def _load_decisions(
    value: str,
    context: CommandContext,
    *,
    synthetic: bool,
) -> tuple[ClaimReviewDecision, ...]:
    path = _authorized_path(value, context, synthetic=synthetic)
    return load_review_decisions(path)


def _authorized_path(
    value: str,
    context: CommandContext,
    *,
    synthetic: bool,
) -> Path:
    path = Path(value)
    if synthetic:
        return path
    assert_outside_git(path)
    return require_private_source(path, context.settings.require_private_root())


def _review_storage_label(synthetic: bool) -> str:
    if synthetic:
        return "synthetic_outside_git"
    return "outside_git_local"


def _claim_view(index: int, claim: AtomicClaimProposal) -> dict[str, object]:
    payload = claim.model_dump(mode="json")
    return {"index": index, **payload}
