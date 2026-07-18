from __future__ import annotations

from pathlib import Path

from ynoy.corpus.codex import assert_synthetic_codex_root, codex_source_key
from ynoy.corpus.codex_approval import verify_codex_approval
from ynoy.corpus.codex_discovery import (
    CodexInventoryLimits,
    DiscoveredCodexFile,
    discover_codex_sessions,
    resolve_codex_root,
)
from ynoy.corpus.raw_vault import RawVaultStore
from ynoy.errors import DataValidationError
from ynoy.models import (
    CodexCorpusApproval,
    CodexInventoryEntry,
    CodexMetadataInventory,
    CodexSnapshotFile,
    CodexSnapshotReceipt,
)
from ynoy.models.codex_vault import SnapshotFileStatus
from ynoy.util import canonical_sha256, new_id, utc_now

_UNSTABLE_CODES = {
    "codex_source_changed_during_inventory",
    "codex_source_changed_during_snapshot",
    "codex_link_swap_rejected",
}


def snapshot_codex_corpus(
    source_root: Path,
    manifest: CodexMetadataInventory,
    approval: CodexCorpusApproval,
    store: RawVaultStore,
    *,
    previous: CodexSnapshotReceipt | None = None,
    max_new_bytes: int | None = None,
    limits: CodexInventoryLimits | None = None,
) -> CodexSnapshotReceipt:
    verify_codex_approval(manifest, approval, operation="snapshot")
    _validate_resume(previous, manifest, approval)
    source = resolve_codex_root(source_root)
    if manifest.synthetic:
        assert_synthetic_codex_root(source)
    discovery = discover_codex_sessions(source, limits or CodexInventoryLimits())
    current = {codex_source_key(item): item for item in discovery.files}
    expected = {item.source_key for item in manifest.entries}
    if set(current) - expected:
        raise DataValidationError(
            "codex_snapshot_unapproved_source",
            "Canonical Codex sources appeared after the approved inventory.",
        )
    files = _snapshot_files(manifest, current, store, previous, max_new_bytes)
    return _build_receipt(manifest, approval, files, previous)


def _snapshot_files(
    manifest: CodexMetadataInventory,
    current: dict[str, DiscoveredCodexFile],
    store: RawVaultStore,
    previous: CodexSnapshotReceipt | None,
    max_new_bytes: int | None,
) -> tuple[CodexSnapshotFile, ...]:
    prior = {item.source_key: item for item in previous.files} if previous else {}
    consumed = 0
    results: list[CodexSnapshotFile] = []
    for expected in manifest.entries:
        existing = prior.get(expected.source_key)
        if existing and existing.status == "vaulted":
            _verify_existing_blob(store, existing)
            results.append(existing)
            continue
        source = current.get(expected.source_key)
        if source is None:
            results.append(_failed_file(expected, "source_missing"))
            continue
        if source.file_bytes != expected.file_bytes:
            results.append(_deferred_file(expected, "deferred_unstable"))
            continue
        if max_new_bytes is not None and consumed + expected.file_bytes > max_new_bytes:
            results.append(_deferred_file(expected, "deferred_rollout"))
            continue
        result = _vault_one(expected, source, store)
        if result.status == "vaulted":
            consumed += result.vaulted_bytes
        results.append(result)
    return tuple(results)


def _vault_one(
    expected: CodexInventoryEntry,
    source: DiscoveredCodexFile,
    store: RawVaultStore,
) -> CodexSnapshotFile:
    try:
        digest, count = store.vault_file(source)
    except DataValidationError as exc:
        if exc.code in _UNSTABLE_CODES:
            return _deferred_file(expected, "deferred_unstable")
        return _failed_file(expected, exc.code)
    return CodexSnapshotFile(
        source_key=expected.source_key,
        partition=expected.partition,
        expected_bytes=expected.file_bytes,
        status="vaulted",
        blob_sha256=digest,
        vaulted_bytes=count,
    )


def _verify_existing_blob(store: RawVaultStore, existing: CodexSnapshotFile) -> None:
    if existing.blob_sha256 is None:
        raise DataValidationError(
            "snapshot_blob_binding_missing", "Snapshot blob binding is missing."
        )
    with store.open_blob(existing.blob_sha256, existing.expected_bytes):
        pass


def _deferred_file(expected: CodexInventoryEntry, status: SnapshotFileStatus) -> CodexSnapshotFile:
    return CodexSnapshotFile(
        source_key=expected.source_key,
        partition=expected.partition,
        expected_bytes=expected.file_bytes,
        status=status,
        vaulted_bytes=0,
    )


def _failed_file(expected: CodexInventoryEntry, code: str) -> CodexSnapshotFile:
    return CodexSnapshotFile(
        source_key=expected.source_key,
        partition=expected.partition,
        expected_bytes=expected.file_bytes,
        status="error",
        vaulted_bytes=0,
        error_code=code,
    )


def _build_receipt(
    manifest: CodexMetadataInventory,
    approval: CodexCorpusApproval,
    files: tuple[CodexSnapshotFile, ...],
    previous: CodexSnapshotReceipt | None,
) -> CodexSnapshotReceipt:
    vaulted = tuple(item for item in files if item.status == "vaulted")
    deferred = tuple(item for item in files if item.status.startswith("deferred_"))
    errors = tuple(item for item in files if item.status == "error")
    status = "complete" if len(vaulted) == len(files) else "partial"
    if errors and not vaulted:
        status = "failed"
    draft = CodexSnapshotReceipt.model_construct(
        record_id=new_id(),
        created_at=utc_now(),
        snapshot_id=previous.snapshot_id if previous else new_id(),
        manifest_id=manifest.record_id,
        manifest_sha256=manifest.manifest_sha256,
        approval_id=approval.record_id,
        approval_sha256=approval.approval_sha256,
        source_data_class=manifest.source_data_class,
        synthetic=manifest.synthetic,
        previous_receipt_sha256=previous.receipt_sha256 if previous else None,
        files=files,
        expected_file_count=len(files),
        expected_bytes=sum(item.expected_bytes for item in files),
        vaulted_file_count=len(vaulted),
        vaulted_bytes=sum(item.vaulted_bytes for item in vaulted),
        deferred_file_count=len(deferred),
        error_file_count=len(errors),
        status=status,
        receipt_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"receipt_sha256"})
    return CodexSnapshotReceipt.model_validate(
        {**draft.model_dump(mode="python"), "receipt_sha256": canonical_sha256(payload)}
    )


def _validate_resume(
    previous: CodexSnapshotReceipt | None,
    manifest: CodexMetadataInventory,
    approval: CodexCorpusApproval,
) -> None:
    if previous is None:
        return
    bindings = (
        previous.manifest_id == manifest.record_id,
        previous.manifest_sha256 == manifest.manifest_sha256,
        previous.approval_id == approval.record_id,
        previous.approval_sha256 == approval.approval_sha256,
        previous.synthetic == manifest.synthetic,
    )
    if not all(bindings):
        raise DataValidationError(
            "codex_snapshot_resume_mismatch",
            "Snapshot resume inputs do not match the previous receipt.",
        )
