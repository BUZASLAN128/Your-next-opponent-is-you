from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ynoy.constants import CODEX_INGEST_TRANSACTION_EVENTS
from ynoy.corpus.codex_approval import verify_codex_approval
from ynoy.corpus.codex_normalizer import normalize_codex_record
from ynoy.corpus.codex_normalizer_types import CodexFileBinding, CodexParserState
from ynoy.corpus.codex_raw_records import iter_jsonl_records
from ynoy.corpus.raw_vault import RawVaultStore
from ynoy.errors import DataValidationError
from ynoy.models import (
    CodexIngestionReceipt,
    CodexMetadataInventory,
    CodexSnapshotReceipt,
    NormalizedCodexEvent,
)
from ynoy.storage.codex_ingestion_repository import (
    CodexIngestionRepository,
    IngestionCheckpoint,
)
from ynoy.util import canonical_sha256, new_id, utc_now


def ingest_codex_snapshot(
    snapshot: CodexSnapshotReceipt,
    manifest: CodexMetadataInventory,
    store: RawVaultStore,
    repository: CodexIngestionRepository,
    *,
    resume: bool,
) -> CodexIngestionReceipt:
    approval = store.read_approval(snapshot.approval_id)
    _verify_inputs(snapshot, manifest, approval.approval_sha256)
    verify_codex_approval(manifest, approval, operation="ingest")
    checkpoints = repository.prepare(snapshot.snapshot_id)
    _verify_checkpoint_bindings(snapshot, checkpoints)
    for checkpoint in checkpoints:
        if checkpoint.status == "complete":
            continue
        if checkpoint.next_byte_offset and not resume:
            raise DataValidationError(
                "codex_ingest_resume_required",
                "An incomplete Codex ingestion requires the explicit resume flag.",
            )
        _ingest_file(store, repository, checkpoint, snapshot)
    return build_ingestion_receipt(snapshot, repository.summary(snapshot.snapshot_id))


def _ingest_file(
    store: RawVaultStore,
    repository: CodexIngestionRepository,
    checkpoint: IngestionCheckpoint,
    snapshot: CodexSnapshotReceipt,
) -> None:
    state = CodexParserState.from_payload(checkpoint.parser_state)
    binding = CodexFileBinding(
        snapshot_id=snapshot.snapshot_id,
        source_key=checkpoint.source_key,
        blob_sha256=checkpoint.blob_sha256,
        data_class=snapshot.source_data_class,
        synthetic=snapshot.synthetic,
    )
    with store.open_blob(checkpoint.blob_sha256, checkpoint.expected_bytes) as stream:
        raw_records = iter_jsonl_records(
            stream,
            start_offset=checkpoint.next_byte_offset,
            completed_lines=checkpoint.completed_lines,
        )
        events = (normalize_codex_record(raw, state, binding) for raw in raw_records)
        current = checkpoint
        for batch in _batches(events):
            current = repository.save_batch(current, batch, state.to_payload())
    if current.next_byte_offset != current.expected_bytes:
        raise DataValidationError(
            "codex_ingest_byte_reconciliation_failed",
            "Normalized event offsets do not reconcile to the complete blob.",
        )


def _batches(events: Iterable[NormalizedCodexEvent]) -> Iterable[list[NormalizedCodexEvent]]:
    batch: list[NormalizedCodexEvent] = []
    for event in events:
        batch.append(event)
        if len(batch) == CODEX_INGEST_TRANSACTION_EVENTS:
            yield batch
            batch = []
    if batch:
        yield batch


def build_ingestion_receipt(
    snapshot: CodexSnapshotReceipt, summary: dict[str, object]
) -> CodexIngestionReceipt:
    complete_files = _summary_count(summary, "complete_files")
    status = (
        "complete"
        if snapshot.status == "complete" and complete_files == snapshot.expected_file_count
        else "partial"
    )
    draft = CodexIngestionReceipt.model_construct(
        record_id=new_id(),
        created_at=utc_now(),
        snapshot_id=snapshot.snapshot_id,
        snapshot_receipt_sha256=snapshot.receipt_sha256,
        source_data_class=snapshot.source_data_class,
        synthetic=snapshot.synthetic,
        normalized_event_count=_summary_count(summary, "event_count"),
        dialogue_event_count=_summary_count(summary, "dialogue_count"),
        safe_action_event_count=_summary_count(summary, "safe_action_count"),
        quarantined_event_count=_summary_count(summary, "quarantined_count"),
        processed_file_count=complete_files,
        processed_bytes=_summary_count(summary, "processed_bytes"),
        status=status,
        receipt_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"receipt_sha256"})
    return CodexIngestionReceipt.model_validate(
        {**draft.model_dump(mode="python"), "receipt_sha256": canonical_sha256(payload)}
    )


def _summary_count(summary: dict[str, object], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, bool):
        valid = None
    elif isinstance(value, int):
        valid = value
    elif isinstance(value, Decimal) and value == value.to_integral_value():
        valid = int(value)
    else:
        valid = None
    if valid is None or valid < 0:
        raise DataValidationError(
            "codex_ingest_summary_invalid", "Codex ingestion summary is invalid."
        )
    return valid


def _verify_inputs(
    snapshot: CodexSnapshotReceipt,
    manifest: CodexMetadataInventory,
    approval_sha256: str,
) -> None:
    if (
        snapshot.manifest_id != manifest.record_id
        or snapshot.manifest_sha256 != manifest.manifest_sha256
        or snapshot.approval_sha256 != approval_sha256
    ):
        raise DataValidationError(
            "codex_ingest_binding_mismatch",
            "Snapshot, inventory, and approval bindings do not match.",
        )


def _verify_checkpoint_bindings(
    snapshot: CodexSnapshotReceipt, checkpoints: tuple[IngestionCheckpoint, ...]
) -> None:
    vaulted = {item.source_key: item for item in snapshot.files if item.status == "vaulted"}
    if len(vaulted) != len(checkpoints):
        raise DataValidationError(
            "codex_ingest_checkpoint_set_mismatch",
            "Checkpoint set does not match the vaulted snapshot files.",
        )
    for checkpoint in checkpoints:
        item = vaulted.get(checkpoint.source_key)
        if (
            item is None
            or item.blob_sha256 != checkpoint.blob_sha256
            or item.expected_bytes != checkpoint.expected_bytes
        ):
            raise DataValidationError(
                "codex_ingest_checkpoint_binding_mismatch",
                "Checkpoint binding does not match its immutable snapshot file.",
            )
