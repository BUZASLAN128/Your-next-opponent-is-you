from __future__ import annotations

from collections.abc import Sequence

from psycopg.types.json import Jsonb

from ynoy.models import AuditReceipt, BenchmarkCase, BenchmarkManifest, BenchmarkRun
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database
from ynoy.util import utc_now


class BenchmarkRepository:
    def __init__(self, database: Database):
        self.database = database

    def save_benchmark(
        self,
        manifest: BenchmarkManifest,
        cases: Sequence[BenchmarkCase],
        audit_receipt: AuditReceipt,
    ) -> None:
        with self.database.connect() as connection:
            for case in cases:
                connection.execute(
                    """
                    INSERT INTO ynoy.benchmark_cases
                        (record_id, case_id, event_time, dependency_cluster_id,
                         record, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (case_id) DO UPDATE SET
                        record = EXCLUDED.record,
                        event_time = EXCLUDED.event_time,
                        dependency_cluster_id = EXCLUDED.dependency_cluster_id
                    """,
                    (
                        case.record_id,
                        case.case_id,
                        case.event_time,
                        case.dependency_cluster_id,
                        Jsonb(case.model_dump(mode="json")),
                        case.created_at,
                    ),
                )
            connection.execute(
                """
                INSERT INTO ynoy.benchmark_manifests
                    (record_id, manifest_sha256, record, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (record_id) DO NOTHING
                """,
                (
                    manifest.record_id,
                    manifest.manifest_sha256,
                    Jsonb(manifest.model_dump(mode="json")),
                    manifest.created_at,
                ),
            )
            insert_audit_receipt(connection, audit_receipt)

    def save_run(self, run: BenchmarkRun, audit_receipt: AuditReceipt) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO ynoy.benchmark_runs (
                    record_id, manifest_id, manifest_sha256, status, config,
                    metrics, fatal_gates, started_at, completed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO NOTHING
                """,
                (
                    run.record_id,
                    run.manifest_id,
                    run.manifest_sha256,
                    run.status,
                    Jsonb(_run_config(run)),
                    Jsonb(run.metrics),
                    list(run.fatal_gates),
                    run.created_at,
                    utc_now(),
                ),
            )
            for prediction in run.predictions:
                connection.execute(
                    """
                    INSERT INTO ynoy.benchmark_predictions
                        (run_id, case_id, algorithm, regime, prediction)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, case_id, algorithm, regime) DO NOTHING
                    """,
                    (
                        run.record_id,
                        prediction.case_id,
                        prediction.algorithm,
                        prediction.regime.value,
                        Jsonb(prediction.model_dump(mode="json")),
                    ),
                )
            insert_audit_receipt(connection, audit_receipt)


def _run_config(run: BenchmarkRun) -> dict[str, object]:
    return {
        "schema_version": run.schema_version,
        "run_sha256": run.run_sha256,
        "local_only": run.local_only,
        "external_calls": list(run.external_calls),
        "evidence_tier": run.evidence_tier,
        "acceptance_status": run.acceptance_status,
    }
