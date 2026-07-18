from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.constants import CODEX_VAULT_VERSION
from ynoy.models.base import DataClass, RecordBase, StrictModel
from ynoy.models.codex_inventory import CodexPartition
from ynoy.util import canonical_sha256

CodexVaultOperation = Literal["snapshot", "ingest", "derive", "benchmark"]
SnapshotFileStatus = Literal[
    "vaulted",
    "deferred_unstable",
    "deferred_rollout",
    "error",
]


class CodexCorpusApproval(RecordBase):
    manifest_id: UUID
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_operations: tuple[CodexVaultOperation, ...]
    retention_days: int | None = Field(default=None, ge=1)
    third_party_reviewed: bool
    approved_by: Literal["represented_user"] = "represented_user"
    approval_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def approval_is_consistent(self) -> CodexCorpusApproval:
        if not self.allowed_operations or len(set(self.allowed_operations)) != len(
            self.allowed_operations
        ):
            raise ValueError("Codex approval operations must be non-empty and unique")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"approval_sha256"}))
        if self.approval_sha256 != expected:
            raise ValueError("Codex approval hash does not match its payload")
        return self


class CodexSnapshotFile(StrictModel):
    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: CodexPartition
    expected_bytes: int = Field(ge=0)
    status: SnapshotFileStatus
    blob_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    vaulted_bytes: int = Field(ge=0)
    error_code: str | None = None

    @model_validator(mode="after")
    def file_state_is_consistent(self) -> CodexSnapshotFile:
        vaulted = self.status == "vaulted"
        if vaulted != (self.blob_sha256 is not None):
            raise ValueError("Only vaulted files may bind a blob hash")
        if vaulted and self.vaulted_bytes != self.expected_bytes:
            raise ValueError("Vaulted byte count must equal inventory bytes")
        if not vaulted and self.vaulted_bytes != 0:
            raise ValueError("Deferred or failed files cannot claim vaulted bytes")
        if (self.status == "error") != (self.error_code is not None):
            raise ValueError("Only error entries require an error code")
        return self


class CodexSnapshotReceipt(RecordBase):
    snapshot_id: UUID
    manifest_id: UUID
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: UUID
    approval_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_version: Literal["codex-raw-vault/1.0"] = CODEX_VAULT_VERSION
    source_data_class: DataClass
    synthetic: bool
    previous_receipt_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    files: tuple[CodexSnapshotFile, ...]
    expected_file_count: int = Field(ge=0)
    expected_bytes: int = Field(ge=0)
    vaulted_file_count: int = Field(ge=0)
    vaulted_bytes: int = Field(ge=0)
    deferred_file_count: int = Field(ge=0)
    error_file_count: int = Field(ge=0)
    byte_reconciliation_percent: Literal[100] = 100
    status: Literal["complete", "partial", "failed"]
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def snapshot_is_consistent(self) -> CodexSnapshotReceipt:
        _validate_snapshot_mode(self)
        _validate_snapshot_counts(self)
        if self.receipt_sha256 != canonical_sha256(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("Snapshot receipt hash does not match its payload")
        return self


def _validate_snapshot_mode(receipt: CodexSnapshotReceipt) -> None:
    expected = DataClass.PUBLIC_SYNTHETIC if receipt.synthetic else DataClass.RAW_CORPUS
    if receipt.source_data_class != expected:
        raise ValueError("Snapshot data class contradicts its mode")
    if len({item.source_key for item in receipt.files}) != len(receipt.files):
        raise ValueError("Snapshot source keys must be unique")


def _validate_snapshot_counts(receipt: CodexSnapshotReceipt) -> None:
    files = receipt.files
    vaulted = tuple(item for item in files if item.status == "vaulted")
    deferred = tuple(item for item in files if item.status.startswith("deferred_"))
    errors = tuple(item for item in files if item.status == "error")
    actual = (
        len(files),
        sum(item.expected_bytes for item in files),
        len(vaulted),
        sum(item.vaulted_bytes for item in vaulted),
        len(deferred),
        len(errors),
    )
    declared = (
        receipt.expected_file_count,
        receipt.expected_bytes,
        receipt.vaulted_file_count,
        receipt.vaulted_bytes,
        receipt.deferred_file_count,
        receipt.error_file_count,
    )
    if actual != declared:
        raise ValueError("Snapshot aggregate counts do not match file receipts")
    expected_status = "complete" if len(vaulted) == len(files) else "partial"
    if errors and not vaulted:
        expected_status = "failed"
    if receipt.status != expected_status:
        raise ValueError("Snapshot status does not match file receipts")
