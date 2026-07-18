from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import build_audit_receipt, parse_uuid, require_matching_mode
from ynoy.corpus.codex_approval import create_codex_approval
from ynoy.corpus.codex_ingest import ingest_codex_snapshot
from ynoy.corpus.codex_snapshot import snapshot_codex_corpus
from ynoy.errors import DataValidationError, YnoyError
from ynoy.models import AuditReceipt, CodexSnapshotReceipt, DataClass
from ynoy.policy import assert_outside_git
from ynoy.storage import CodexIngestionRepository, CorpusVaultRepository


def approve_codex(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = context.raw_vault(synthetic=synthetic)
    manifest = store.read_manifest(parse_uuid(args.manifest_id, "manifest_id"))
    require_matching_mode(requested_synthetic=synthetic, artifact_synthetic=manifest.synthetic)
    operations = tuple(args.operations or ("snapshot", "ingest", "derive", "benchmark"))
    approval = create_codex_approval(
        manifest,
        allowed_operations=operations,
        retention_days=args.retention_days,
        third_party_reviewed=bool(args.third_party_reviewed),
    )
    store.write_approval(approval)
    try:
        inserted = CorpusVaultRepository(context.database(synthetic=synthetic)).save_approval(
            approval,
            _approval_audit(approval.record_id, manifest.source_data_class),
            synthetic=synthetic,
        )
    except YnoyError:
        store.delete_approval(approval.record_id)
        raise
    return {
        "status": "codex_approved" if inserted else "codex_already_approved",
        "approval_id": str(approval.record_id),
        "allowed_operations": list(approval.allowed_operations),
        "private_content_emitted": False,
    }


def snapshot_codex(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source_root = Path(args.codex_root)
    if not synthetic:
        assert_outside_git(source_root)
    if args.max_new_bytes is not None and args.max_new_bytes < 1:
        raise DataValidationError(
            "codex_snapshot_byte_limit_invalid", "Snapshot byte limit must be positive."
        )
    store = context.raw_vault(synthetic=synthetic)
    manifest = store.read_manifest(parse_uuid(args.manifest_id, "manifest_id"))
    approval = store.read_approval(parse_uuid(args.approval_id, "approval_id"))
    previous = _previous_snapshot(args, store)
    receipt = snapshot_codex_corpus(
        source_root,
        manifest,
        approval,
        store,
        previous=previous,
        max_new_bytes=args.max_new_bytes,
    )
    store.write_snapshot(receipt)
    inserted = CorpusVaultRepository(context.database(synthetic=synthetic)).save_snapshot(
        receipt, _snapshot_audit(receipt)
    )
    return _snapshot_result(receipt, inserted)


def codex_status(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    snapshot_id = parse_uuid(args.snapshot_id, "snapshot_id")
    state = context.raw_vault(synthetic=synthetic).read_snapshot(snapshot_id)
    database_state = CorpusVaultRepository(context.database(synthetic=synthetic)).status(
        snapshot_id
    )
    if str(database_state["latest_receipt_id"]) != str(state.record_id):
        raise DataValidationError(
            "codex_snapshot_state_mismatch",
            "Raw-vault and PostgreSQL snapshot state do not match.",
        )
    return _snapshot_result(state, inserted=False)


def ingest_codex(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = context.raw_vault(synthetic=synthetic)
    snapshot = store.read_snapshot(parse_uuid(args.snapshot_id, "snapshot_id"))
    manifest = store.read_manifest(snapshot.manifest_id)
    database = context.database(synthetic=synthetic)
    repository = CodexIngestionRepository(database)
    receipt = ingest_codex_snapshot(snapshot, manifest, store, repository, resume=bool(args.resume))
    inserted = repository.save_receipt(receipt, _ingestion_audit(receipt))
    return {
        "status": receipt.status,
        "snapshot_id": str(receipt.snapshot_id),
        "receipt_persisted": inserted,
        "processed_files": receipt.processed_file_count,
        "processed_bytes": receipt.processed_bytes,
        "normalized_events": receipt.normalized_event_count,
        "dialogue_events": receipt.dialogue_event_count,
        "safe_action_events": receipt.safe_action_event_count,
        "quarantined_events": receipt.quarantined_event_count,
        "private_content_emitted": False,
        "model_provider_used": False,
    }


def _previous_snapshot(args: argparse.Namespace, store: object) -> CodexSnapshotReceipt | None:
    from ynoy.corpus.raw_vault import RawVaultStore

    if not args.resume_snapshot_id:
        return None
    if not isinstance(store, RawVaultStore):
        raise TypeError("expected raw vault store")
    return store.read_snapshot(parse_uuid(args.resume_snapshot_id, "resume_snapshot_id"))


def _approval_audit(approval_id: object, data_class: DataClass) -> AuditReceipt:
    return build_audit_receipt(
        event_type="approval",
        reason_code="represented_user_codex_corpus_approval",
        input_ids=(),
        data_classes=(data_class,),
        artifact_id=str(approval_id),
    )


def _snapshot_audit(receipt: CodexSnapshotReceipt) -> AuditReceipt:
    return build_audit_receipt(
        event_type="snapshot",
        reason_code="approved_lossless_content_addressed_snapshot",
        input_ids=(),
        data_classes=(receipt.source_data_class,),
        artifact_id=str(receipt.snapshot_id),
    )


def _ingestion_audit(receipt: object) -> AuditReceipt:
    from ynoy.models import CodexIngestionReceipt

    if not isinstance(receipt, CodexIngestionReceipt):
        raise TypeError("expected Codex ingestion receipt")
    return build_audit_receipt(
        event_type="ingest",
        reason_code="approved_bounded_origin_preserving_codex_normalization",
        input_ids=(str(receipt.snapshot_id),),
        data_classes=(receipt.source_data_class,),
        artifact_id=str(receipt.record_id),
    )


def _snapshot_result(receipt: CodexSnapshotReceipt, inserted: bool) -> dict[str, object]:
    return {
        "status": receipt.status,
        "snapshot_id": str(receipt.snapshot_id),
        "receipt_persisted": inserted,
        "expected_files": receipt.expected_file_count,
        "vaulted_files": receipt.vaulted_file_count,
        "deferred_files": receipt.deferred_file_count,
        "error_files": receipt.error_file_count,
        "expected_bytes": receipt.expected_bytes,
        "vaulted_bytes": receipt.vaulted_bytes,
        "byte_reconciliation_percent": receipt.byte_reconciliation_percent,
        "private_content_emitted": False,
        "model_provider_used": False,
    }
