from __future__ import annotations

import argparse

from ynoy.artifacts import PrivateArtifactStore
from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import parse_uuid
from ynoy.storage import ErasureRepository

JSON_CATEGORIES = (
    "manifests",
    "approvals",
    "receipts",
    "benchmark-manifests",
    "benchmark-case-sets",
    "benchmark-runs",
)


def handle_erase(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    handlers = {"plan": _plan, "confirm": _confirm}
    return handlers[args.erase_command](args, context)


def _plan(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = context.artifacts(synthetic=synthetic)
    repository = ErasureRepository(context.database(synthetic=synthetic))
    plan = repository.plan(source_id=args.source_id)
    path = store.write_json("erasure-plans", str(plan["plan_id"]), plan)
    return {
        "status": "planned",
        **plan,
        "plan_path": str(path),
        "confirmation_required": True,
    }


def _confirm(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = context.artifacts(synthetic=synthetic)
    repository = ErasureRepository(context.database(synthetic=synthetic))
    plan_id = parse_uuid(args.plan_id, "plan_id")
    result = repository.confirm_database(plan_id=plan_id, plan_sha256=args.plan_sha256)
    deleted_artifacts = _delete_artifacts(store, result["artifact_ids"])
    store.delete_if_exists("erasure-plans", plan_id)
    repository.finalize(plan_id=plan_id, plan_sha256=args.plan_sha256)
    return {
        "status": "partial",
        "plan_id": str(plan_id),
        "deleted_record_count": result["deleted_record_count"],
        "deleted_artifact_count": deleted_artifacts,
        "target_counts": result["target_counts"],
        "local_deleted": True,
        "local_database_status": result["status"],
        "universal_success": False,
        "missing_proofs": (
            "independent_producer_universe_attestation",
            "persistent_cross_restart_tombstone_fence",
            "post_delete_future_trace_independence",
        ),
        "provider_residual": "not_applicable_no_external_egress",
        "secure_physical_erase_guaranteed": False,
    }


def _delete_artifacts(store: PrivateArtifactStore, raw_ids: object) -> int:
    if not isinstance(raw_ids, list):
        raise TypeError("artifact ID contract violated")
    deleted = 0
    for artifact_id in raw_ids:
        for category in JSON_CATEGORIES:
            deleted += int(store.delete_if_exists(category, str(artifact_id)))
        deleted += int(store.delete_if_exists("reports", str(artifact_id), ".md"))
    return deleted
