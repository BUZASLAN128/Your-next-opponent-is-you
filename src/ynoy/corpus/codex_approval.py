from __future__ import annotations

from typing import cast

from ynoy.corpus.codex import verify_codex_metadata_inventory
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import CodexCorpusApproval, CodexMetadataInventory
from ynoy.models.codex_vault import CodexVaultOperation
from ynoy.util import canonical_sha256, new_id, utc_now


def create_codex_approval(
    manifest: CodexMetadataInventory,
    *,
    allowed_operations: tuple[str, ...],
    retention_days: int | None,
    third_party_reviewed: bool,
) -> CodexCorpusApproval:
    verify_codex_metadata_inventory(manifest)
    valid = {"snapshot", "ingest", "derive", "benchmark"}
    requested = set(allowed_operations)
    if not requested or not requested <= valid:
        raise DataValidationError(
            "codex_approval_operations_invalid",
            "Codex approval operations are empty or unsupported.",
        )
    operations = cast(tuple[CodexVaultOperation, ...], tuple(sorted(requested)))
    draft = CodexCorpusApproval.model_construct(
        record_id=new_id(),
        created_at=utc_now(),
        manifest_id=manifest.record_id,
        manifest_sha256=manifest.manifest_sha256,
        allowed_operations=operations,
        retention_days=retention_days,
        third_party_reviewed=third_party_reviewed,
        approval_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"approval_sha256"})
    return CodexCorpusApproval.model_validate(
        {**draft.model_dump(mode="python"), "approval_sha256": canonical_sha256(payload)}
    )


def verify_codex_approval(
    manifest: CodexMetadataInventory,
    approval: CodexCorpusApproval,
    *,
    operation: CodexVaultOperation,
) -> None:
    verify_codex_metadata_inventory(manifest)
    safe = CodexCorpusApproval.model_validate(approval.model_dump(mode="python"))
    if safe.manifest_id != manifest.record_id or safe.manifest_sha256 != manifest.manifest_sha256:
        raise DataValidationError(
            "codex_approval_manifest_mismatch",
            "Codex approval does not belong to this inventory.",
        )
    if operation not in safe.allowed_operations:
        raise PolicyViolation(
            "codex_operation_not_approved",
            "The represented-user approval does not authorize this Codex operation.",
        )
    if not manifest.synthetic and not safe.third_party_reviewed:
        raise PolicyViolation(
            "third_party_review_required",
            "Real Codex corpus processing requires third-party-data review declaration.",
        )
