from __future__ import annotations

from typing import Literal, cast

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import IngestionApproval, InventoryManifest
from ynoy.util import canonical_sha256

AllowedOperation = Literal["ingest", "derive", "benchmark", "report"]


def verify_manifest(manifest: InventoryManifest) -> None:
    expected = canonical_sha256(manifest.model_dump(mode="json", exclude={"manifest_sha256"}))
    if manifest.manifest_sha256 != expected:
        raise DataValidationError(
            "manifest_digest_mismatch", "Inventory manifest failed its integrity check."
        )


def create_ingestion_approval(
    manifest: InventoryManifest,
    *,
    allowed_operations: tuple[str, ...],
    retention_days: int | None,
    third_party_reviewed: bool,
) -> IngestionApproval:
    verify_manifest(manifest)
    valid = {"ingest", "derive", "benchmark", "report"}
    requested = set(allowed_operations)
    if not requested or not requested <= valid:
        raise DataValidationError(
            "approval_operations_invalid", "Approval operations are empty or unsupported."
        )
    operations = cast(tuple[AllowedOperation, ...], tuple(sorted(requested)))
    draft = IngestionApproval(
        manifest_id=manifest.record_id,
        manifest_sha256=manifest.manifest_sha256,
        allowed_operations=operations,
        retention_days=retention_days,
        third_party_reviewed=third_party_reviewed,
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"approval_sha256"}))
    return draft.model_copy(update={"approval_sha256": digest})


def verify_approval(manifest: InventoryManifest, approval: IngestionApproval) -> None:
    verify_manifest(manifest)
    expected = canonical_sha256(approval.model_dump(mode="json", exclude={"approval_sha256"}))
    if approval.approval_sha256 != expected:
        raise DataValidationError(
            "approval_digest_mismatch", "Ingestion approval failed its integrity check."
        )
    manifest_matches = (
        approval.manifest_id == manifest.record_id
        and approval.manifest_sha256 == manifest.manifest_sha256
    )
    if not manifest_matches:
        raise DataValidationError(
            "approval_manifest_mismatch", "Approval does not belong to this inventory."
        )
    if "ingest" not in approval.allowed_operations:
        raise PolicyViolation("ingestion_not_approved", "Approval does not authorize ingestion.")
    if not manifest.synthetic and not approval.third_party_reviewed:
        raise PolicyViolation(
            "third_party_review_required",
            "Real-corpus ingestion requires an explicit third-party-data review declaration.",
        )
