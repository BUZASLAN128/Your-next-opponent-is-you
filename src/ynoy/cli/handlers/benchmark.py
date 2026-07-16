from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from ynoy.benchmark import freeze_benchmark, load_benchmark_cases, run_benchmark
from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import append_audit, build_audit_receipt, parse_uuid
from ynoy.errors import DataValidationError, YnoyError
from ynoy.models import BenchmarkCase, BenchmarkManifest, BenchmarkRun, DataClass
from ynoy.report import render_benchmark_markdown
from ynoy.storage import BenchmarkRepository

CASE_LIST_ADAPTER = TypeAdapter(list[BenchmarkCase])


def handle_benchmark(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    handlers = {"freeze": _freeze, "run": _run, "report": _report}
    return handlers[args.benchmark_command](args, context)


def _freeze(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    store = context.artifacts(synthetic=True)
    database = context.database(synthetic=True)
    cases = load_benchmark_cases(Path(args.cases))
    manifest = freeze_benchmark(
        args.name,
        cases,
        development_fraction=float(args.development_fraction),
    )
    manifest_path = store.write_model("benchmark-manifests", manifest.record_id, manifest)
    store.write_json(
        "benchmark-case-sets",
        manifest.record_id,
        [case.model_dump(mode="json") for case in cases],
    )
    audit = build_audit_receipt(
        event_type="derive",
        reason_code="synthetic_temporal_benchmark_frozen",
        input_ids=(str(manifest.record_id),),
        data_classes=(DataClass.PUBLIC_SYNTHETIC,),
        artifact_id=str(manifest.record_id),
    )
    try:
        BenchmarkRepository(database).save_benchmark(manifest, cases, audit)
    except YnoyError:
        store.delete_if_exists("benchmark-manifests", manifest.record_id)
        store.delete_if_exists("benchmark-case-sets", manifest.record_id)
        raise
    return {
        "status": "frozen",
        "manifest_id": str(manifest.record_id),
        "manifest_sha256": manifest.manifest_sha256,
        "manifest_path": str(manifest_path),
        "development_cases": len(manifest.development_case_ids),
        "sealed_cases": len(manifest.sealed_case_ids),
        "thresholds": "not_calibrated",
    }


def _run(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    store = context.artifacts(synthetic=True)
    database = context.database(synthetic=True)
    manifest_id = parse_uuid(args.manifest_id, "manifest_id")
    manifest = store.read_model("benchmark-manifests", manifest_id, BenchmarkManifest)
    cases = _read_cases(store.read_json("benchmark-case-sets", manifest_id))
    run = run_benchmark(manifest, cases)
    path = store.write_model("benchmark-runs", run.record_id, run)
    audit = build_audit_receipt(
        event_type="report",
        reason_code="synthetic_sealed_protocol_run",
        input_ids=(str(manifest.record_id),),
        data_classes=(DataClass.PUBLIC_SYNTHETIC,),
        artifact_id=str(run.record_id),
    )
    try:
        BenchmarkRepository(database).save_run(run, audit)
    except YnoyError:
        store.delete_if_exists("benchmark-runs", run.record_id)
        raise
    return {
        "status": run.status,
        "run_id": str(run.record_id),
        "run_sha256": run.run_sha256,
        "run_path": str(path),
        "acceptance_status": run.acceptance_status,
        "fatal_gates": list(run.fatal_gates),
        "metrics": run.metrics,
        "evidence_tier": run.evidence_tier,
    }


def _read_cases(raw: object) -> list[BenchmarkCase]:
    try:
        return CASE_LIST_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise DataValidationError(
            "benchmark_case_artifact_invalid", "Frozen benchmark cases are invalid."
        ) from exc


def _report(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    store = context.artifacts(synthetic=True)
    manifest = store.read_model(
        "benchmark-manifests", parse_uuid(args.manifest_id, "manifest_id"), BenchmarkManifest
    )
    run = store.read_model("benchmark-runs", parse_uuid(args.run_id, "run_id"), BenchmarkRun)
    if run.manifest_id != manifest.record_id:
        raise DataValidationError(
            "benchmark_report_manifest_mismatch", "Run does not belong to this manifest."
        )
    path = store.write_markdown("reports", run.record_id, render_benchmark_markdown(manifest, run))
    database = context.database(synthetic=True)
    try:
        append_audit(
            database,
            event_type="report",
            reason_code="synthetic_private_report_written",
            input_ids=(str(manifest.record_id), str(run.record_id)),
            data_classes=(DataClass.PUBLIC_SYNTHETIC,),
            artifact_id=str(run.record_id),
        )
    except YnoyError:
        store.delete_if_exists("reports", run.record_id, ".md")
        raise
    return {
        "status": "reported",
        "report_path": str(path),
        "local_only": run.local_only,
        "external_calls": len(run.external_calls),
        "evidence_tier": run.evidence_tier,
    }
