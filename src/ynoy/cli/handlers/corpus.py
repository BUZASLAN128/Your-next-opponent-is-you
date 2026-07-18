from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import build_audit_receipt, parse_uuid, require_matching_mode
from ynoy.cli.handlers.corpus_codex_vault import (
    approve_codex,
    codex_status,
    ingest_codex,
    snapshot_codex,
)
from ynoy.corpus import (
    ChatGPTZipAdapter,
    CodexContentSampleAdapter,
    CodexMetadataAdapter,
    create_ingestion_approval,
    verify_approval,
)
from ynoy.errors import YnoyError
from ynoy.models import AuditReceipt, DataClass, IngestionApproval, InventoryManifest, SourceReceipt
from ynoy.policy import assert_outside_git, require_private_root
from ynoy.report import render_inventory_markdown
from ynoy.storage import CorpusRepository
from ynoy.util import new_id


def handle_corpus(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    handlers = {
        "inventory": _inventory,
        "codex-inventory": _codex_inventory,
        "codex-pilot": _codex_pilot,
        "codex-snapshot": snapshot_codex,
        "codex-ingest": ingest_codex,
        "status": codex_status,
        "approve": _approve,
        "ingest": _ingest,
    }
    return handlers[args.corpus_command](args, context)


def _codex_pilot(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    private_root = context.settings.require_private_root()
    require_private_root(private_root, real_data=not synthetic)
    source_root = Path(args.codex_root)
    if not synthetic:
        assert_outside_git(source_root)
    sample = CodexContentSampleAdapter().sample(source_root, synthetic=synthetic)
    return {
        "status": "content_sampled_ephemerally",
        "summary": sample.summary.model_dump(mode="json"),
    }


def _codex_inventory(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source_root = Path(args.codex_root)
    if not synthetic:
        assert_outside_git(source_root)
    store = context.metadata_inventory_artifacts(synthetic=synthetic)
    manifest = CodexMetadataAdapter().inventory(source_root, synthetic=synthetic)
    manifest_path = store.write_manifest(manifest)
    return {
        "status": "metadata_inventoried",
        "manifest_id": str(manifest.record_id),
        "manifest_sha256": manifest.manifest_sha256,
        "metadata_snapshot_sha256": manifest.metadata_snapshot_sha256,
        "manifest_path": str(manifest_path),
        "storage_protection": store.storage_protection,
        "counts": {
            "entries": manifest.entry_count,
            "bytes": manifest.total_bytes,
            "ignored_noncanonical_files": manifest.ignored_noncanonical_file_count,
            "states": manifest.state_counts,
            "partitions": manifest.partition_counts,
        },
        "content_fields_copied": False,
        "claims_derived": 0,
        "database_used": False,
        "model_provider_used": False,
    }


def _inventory(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    archive_path = Path(args.archive)
    if not synthetic:
        assert_outside_git(archive_path)
    store = context.artifacts(synthetic=synthetic)
    database = context.database(synthetic=synthetic)
    manifest = ChatGPTZipAdapter().inventory(archive_path, synthetic=synthetic)
    manifest_path = store.write_model("manifests", manifest.record_id, manifest)
    report_path = None
    if args.markdown_report:
        report_path = store.write_markdown(
            "reports", manifest.record_id, render_inventory_markdown(manifest)
        )
    audit = build_audit_receipt(
        event_type="inventory",
        reason_code="metadata_only_no_claim_derivation",
        input_ids=(str(manifest.record_id),),
        data_classes=(manifest.source_data_class,),
        artifact_id=str(manifest.record_id),
    )
    try:
        CorpusRepository(database).save_inventory(manifest, audit)
    except YnoyError:
        store.delete_if_exists("manifests", manifest.record_id)
        if report_path:
            store.delete_if_exists("reports", manifest.record_id, ".md")
        raise
    return {
        "status": "inventoried",
        "manifest_id": str(manifest.record_id),
        "manifest_sha256": manifest.manifest_sha256,
        "erasure_source_id": manifest.source_archive_sha256,
        "manifest_path": str(manifest_path),
        "report_path": str(report_path) if report_path else None,
        "counts": _inventory_counts(manifest),
        "claims_derived": 0,
    }


def _inventory_counts(manifest: InventoryManifest) -> dict[str, int]:
    return {
        "entries": manifest.entry_count,
        "conversations": manifest.conversation_count,
        "messages": manifest.message_count,
        "branches": manifest.branch_count,
        "malformed": manifest.malformed_record_count,
        "excluded_content_parts": manifest.excluded_content_part_count,
    }


def _approve(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    if args.codex:
        return approve_codex(args, context)
    synthetic = bool(args.synthetic)
    store = context.artifacts(synthetic=synthetic)
    database = context.database(synthetic=synthetic)
    manifest = store.read_model(
        "manifests", parse_uuid(args.manifest_id, "manifest_id"), InventoryManifest
    )
    require_matching_mode(requested_synthetic=synthetic, artifact_synthetic=manifest.synthetic)
    approval = create_ingestion_approval(
        manifest,
        allowed_operations=tuple(args.operations or ("ingest", "derive", "benchmark", "report")),
        retention_days=args.retention_days,
        third_party_reviewed=bool(args.third_party_reviewed),
    )
    path = store.write_model("approvals", approval.record_id, approval)
    audit = build_audit_receipt(
        event_type="approval",
        reason_code="represented_user_scoped_approval",
        input_ids=(str(manifest.record_id),),
        data_classes=(manifest.source_data_class,),
        artifact_id=str(approval.record_id),
    )
    try:
        CorpusRepository(database).save_approval(approval, audit)
    except YnoyError:
        store.delete_if_exists("approvals", approval.record_id)
        raise
    return {
        "status": "approved",
        "approval_id": str(approval.record_id),
        "approval_sha256": approval.approval_sha256,
        "approval_path": str(path),
    }


def _ingest(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    archive_path = Path(args.archive)
    if not synthetic:
        assert_outside_git(archive_path)
    store = context.artifacts(synthetic=synthetic)
    database = context.database(synthetic=synthetic)
    manifest = store.read_model(
        "manifests", parse_uuid(args.manifest_id, "manifest_id"), InventoryManifest
    )
    approval = store.read_model(
        "approvals", parse_uuid(args.approval_id, "approval_id"), IngestionApproval
    )
    require_matching_mode(requested_synthetic=synthetic, artifact_synthetic=manifest.synthetic)
    verify_approval(manifest, approval)
    adapter = ChatGPTZipAdapter()
    import_run_id = new_id()
    events = adapter.iter_events(archive_path, manifest=manifest, import_run_id=import_run_id)
    repository = CorpusRepository(database)
    inserted, receipt = repository.ingest_events(
        events,
        lambda count: adapter.build_receipt(
            manifest=manifest, import_run_id=import_run_id, normalized_count=count
        ),
        lambda value: _ingest_audit(value, manifest, approval, synthetic),
    )
    return {
        "status": "ingested",
        "import_run_id": str(import_run_id),
        "erasure_source_id": manifest.source_archive_sha256,
        "normalized_events": receipt.normalized_event_count,
        "inserted_events": inserted,
        "excluded_events": receipt.excluded_event_count,
        "idempotent_replay_count": receipt.normalized_event_count - inserted,
    }


def _ingest_audit(
    receipt: SourceReceipt,
    manifest: InventoryManifest,
    approval: IngestionApproval,
    synthetic: bool,
) -> AuditReceipt:
    return build_audit_receipt(
        event_type="ingest",
        reason_code="approved_origin_preserving_normalization",
        input_ids=(str(manifest.record_id), str(approval.record_id)),
        data_classes=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS,),
        artifact_id=str(receipt.record_id),
    )
