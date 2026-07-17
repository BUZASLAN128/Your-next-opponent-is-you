from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from ynoy.canonical_admission import build_canonical_admission
from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import build_audit_receipt, parse_uuid, require_matching_mode
from ynoy.errors import DataValidationError
from ynoy.models import (
    AuditReceipt,
    CandidateKind,
    CanonicalClaimAdmission,
    DecisionLabel,
    InteractionCorrectionReceipt,
    InteractionReview,
    PersonaStratum,
)
from ynoy.policy import assert_outside_git, require_private_source
from ynoy.review_files import load_review_model
from ynoy.storage import CanonicalClaimRepository


def admit_canonical_claim(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    review = _load_model(
        args.review, context, InteractionReview, synthetic=synthetic, label="interaction_review"
    )
    require_matching_mode(requested_synthetic=synthetic, artifact_synthetic=review.source.synthetic)
    receipts = tuple(
        _load_model(
            value,
            context,
            InteractionCorrectionReceipt,
            synthetic=synthetic,
            label="correction_receipt",
        )
        for value in args.receipt
    )
    if any(item.synthetic != synthetic for item in receipts):
        raise DataValidationError(
            "canonical_admission_mode_mismatch", "Admission receipts cross the data boundary."
        )
    admission = _build_admission(args, review, receipts)
    database = context.database(synthetic=synthetic)
    inserted = CanonicalClaimRepository(database, data_class=admission.claim.data_class).admit(
        admission, _admission_audit(review, receipts, admission)
    )
    return _admission_result(admission, inserted)


def _build_admission(
    args: argparse.Namespace,
    review: InteractionReview,
    receipts: tuple[InteractionCorrectionReceipt, ...],
) -> CanonicalClaimAdmission:
    return build_canonical_admission(
        review,
        receipts,
        effective_claim_id=parse_uuid(args.claim_id, "claim_id"),
        persona_kind=CandidateKind(args.persona_kind) if args.persona_kind else None,
        persona_stratum=PersonaStratum(args.persona_stratum) if args.persona_stratum else None,
        decision_label=DecisionLabel(args.decision_label) if args.decision_label else None,
        supersedes_claim_id=(
            parse_uuid(args.supersedes_claim_id, "supersedes_claim_id")
            if args.supersedes_claim_id
            else None
        ),
    )


def _admission_audit(
    review: InteractionReview,
    receipts: tuple[InteractionCorrectionReceipt, ...],
    admission: CanonicalClaimAdmission,
) -> AuditReceipt:
    return build_audit_receipt(
        event_type="derive",
        reason_code="explicit_user_canonical_claim_admission",
        input_ids=(str(review.source.record_id), *(str(item.record_id) for item in receipts)),
        data_classes=(admission.claim.data_class,),
        artifact_id=str(admission.claim.record_id),
    )


def _admission_result(admission: CanonicalClaimAdmission, inserted: bool) -> dict[str, object]:
    return {
        "status": "admitted" if inserted else "already_admitted",
        "claim_id": str(admission.claim.record_id),
        "admission_receipt_id": str(admission.receipt.record_id),
        "target_layer": admission.claim.target_layer.value,
        "source_count": len(admission.source_links),
        "automatic_core_promotion": False,
    }


def _load_model[T: BaseModel](
    value: str,
    context: CommandContext,
    model: type[T],
    *,
    synthetic: bool,
    label: str,
) -> T:
    path = Path(value)
    if not synthetic:
        assert_outside_git(path)
        path = require_private_source(path, context.settings.require_private_root())
    return load_review_model(path, model, label=label)
