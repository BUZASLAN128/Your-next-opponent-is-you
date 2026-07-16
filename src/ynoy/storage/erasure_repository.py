from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.constants import SCHEMA_VERSION
from ynoy.errors import DataValidationError
from ynoy.models import AuditReceipt
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database, Row, require_row
from ynoy.util import canonical_sha256, new_id, utc_now

TARGETS_SQL = """
WITH RECURSIVE requested(value) AS (VALUES (%s)), seeds(record_id) AS (
    SELECT event.record_id FROM ynoy.source_events event, requested
    WHERE event.source_id = requested.value OR event.record_id::text = requested.value
    UNION
    SELECT receipt.record_id FROM ynoy.source_receipts receipt, requested
    WHERE receipt.source_id = requested.value
    UNION
    SELECT manifest.record_id FROM ynoy.inventory_manifests manifest, requested
    WHERE manifest.source_archive_sha256 = requested.value
    UNION
    SELECT approval.record_id
    FROM ynoy.ingestion_approvals approval
    JOIN ynoy.inventory_manifests manifest ON manifest.record_id = approval.manifest_id
    CROSS JOIN requested
    WHERE manifest.source_archive_sha256 = requested.value
    UNION
    SELECT source.record_id FROM ynoy.bootstrap_sources source, requested
    WHERE source.record_id::text = requested.value
    UNION
    SELECT declaration.record_id FROM ynoy.bootstrap_declarations declaration, requested
    WHERE declaration.record_id::text = requested.value
       OR declaration.source_record_id::text = requested.value
    UNION
    SELECT claim.record_id FROM ynoy.claim_candidates claim, requested
    WHERE claim.record_id::text = requested.value
    UNION
    SELECT identity.record_id FROM ynoy.identity_candidates identity, requested
    WHERE identity.record_id::text = requested.value
    UNION
    SELECT report.record_id FROM ynoy.private_reports report, requested
    WHERE report.record_id::text = requested.value
), targets(record_id) AS (
    SELECT record_id FROM seeds
    UNION
    SELECT edge.derived_record_id
    FROM ynoy.derivation_edges edge
    JOIN targets ON targets.record_id = edge.source_record_id
)
SELECT record_id FROM targets ORDER BY record_id
"""


class ErasureRepository:
    def __init__(self, database: Database):
        self.database = database

    def plan(self, *, source_id: str, ttl_minutes: int = 30) -> dict[str, object]:
        with self.database.connect() as connection:
            target_ids = _target_ids(connection, source_id)
            if not target_ids:
                raise DataValidationError(
                    "erasure_source_not_found", "No private records match this source ID."
                )
            counts = _target_counts(connection, source_id, target_ids)
            plan_id = new_id()
            expires_at = utc_now() + timedelta(minutes=ttl_minutes)
            payload = {
                "plan_id": str(plan_id),
                "source_id": source_id,
                "target_record_ids": [str(value) for value in target_ids],
                "target_counts": counts,
                "expires_at": expires_at.isoformat(),
            }
            plan_sha256 = canonical_sha256(payload)
            connection.execute(
                """
                INSERT INTO ynoy.erasure_plans (
                    record_id, source_id, target_record_ids, target_counts,
                    plan_sha256, expires_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (plan_id, source_id, target_ids, Jsonb(counts), plan_sha256, expires_at, utc_now()),
            )
            _append_erasure_plan_receipt(connection, plan_id, len(target_ids))
        return {**payload, "plan_sha256": plan_sha256}

    def confirm_database(self, *, plan_id: UUID, plan_sha256: str) -> dict[str, object]:
        with self.database.connect() as connection:
            plan = _lock_plan(connection, plan_id, plan_sha256)
            target_ids = list(plan["target_record_ids"])
            source_id = str(plan["source_id"])
            if plan["confirmed_at"] is None:
                _assert_current_targets(connection, source_id, target_ids)
                _delete_targets(connection, source_id, target_ids)
                connection.execute(
                    "UPDATE ynoy.erasure_plans SET confirmed_at = %s WHERE record_id = %s",
                    (utc_now(), plan_id),
                )
                _append_database_delete_receipt(connection, plan_id, len(target_ids))
        return {
            "plan_id": str(plan_id),
            "source_id": source_id,
            "deleted_record_count": len(target_ids),
            "target_counts": plan["target_counts"],
            "artifact_ids": [str(value) for value in target_ids],
            "database_deleted": True,
        }

    def finalize(self, *, plan_id: UUID, plan_sha256: str) -> None:
        with self.database.connect() as connection:
            plan = _lock_plan(connection, plan_id, plan_sha256)
            if plan["confirmed_at"] is None:
                raise DataValidationError(
                    "erasure_database_not_confirmed",
                    "Database deletion must complete before artifact cleanup is finalized.",
                )
            _append_tombstone(connection, plan_id, len(plan["target_record_ids"]))
            connection.execute("DELETE FROM ynoy.erasure_plans WHERE record_id = %s", (plan_id,))


def _target_ids(connection: Connection[Row], source_id: str) -> list[UUID]:
    rows = connection.execute(TARGETS_SQL, (source_id,)).fetchall()
    return [row["record_id"] for row in rows]


def _count_any(connection: Connection[Row], table: str, column: str, ids: list[UUID]) -> int:
    row = connection.execute(
        f"SELECT count(*) AS count FROM ynoy.{table} WHERE {column} = ANY(%s::uuid[])",
        (ids,),
    ).fetchone()
    return int(require_row(row, f"{table} erasure count")["count"])


def _target_counts(
    connection: Connection[Row], source_id: str, target_ids: list[UUID]
) -> dict[str, int]:
    counts = {
        table: _count_any(connection, table, "record_id", target_ids)
        for table in (
            "source_events",
            "inventory_manifests",
            "ingestion_approvals",
            "bootstrap_sources",
            "bootstrap_declarations",
            "claim_candidates",
            "identity_candidates",
            "continuity_events",
        )
    }
    for table in ("decision_events", "control_records"):
        counts[table] = _count_any(connection, table, "source_event_id", target_ids)
    counts["source_receipts"] = _source_receipt_count(connection, source_id)
    counts["private_reports"] = _report_count(connection, target_ids)
    return counts


def _source_receipt_count(connection: Connection[Row], source_id: str) -> int:
    row = connection.execute(
        "SELECT count(*) AS count FROM ynoy.source_receipts WHERE source_id = %s",
        (source_id,),
    ).fetchone()
    return int(require_row(row, "source receipt erasure count")["count"])


def _report_count(connection: Connection[Row], ids: list[UUID]) -> int:
    row = connection.execute(
        """
        SELECT count(*) AS count FROM ynoy.private_reports
        WHERE record_id = ANY(%s::uuid[]) OR source_record_ids && %s::uuid[]
        """,
        (ids, ids),
    ).fetchone()
    return int(require_row(row, "private report erasure count")["count"])


def _lock_plan(connection: Connection[Row], plan_id: UUID, digest: str) -> Row:
    plan = connection.execute(
        """
        SELECT source_id, target_record_ids, target_counts, plan_sha256,
               expires_at, confirmed_at
        FROM ynoy.erasure_plans WHERE record_id = %s FOR UPDATE
        """,
        (plan_id,),
    ).fetchone()
    if plan is None:
        raise DataValidationError("erasure_plan_not_found", "Erasure plan was not found.")
    if plan["confirmed_at"] is None and plan["expires_at"] <= utc_now():
        raise DataValidationError("erasure_plan_expired", "Erasure plan has expired.")
    if plan["plan_sha256"] != digest:
        raise DataValidationError(
            "erasure_plan_digest_mismatch", "Erasure confirmation digest does not match."
        )
    return plan


def _assert_current_targets(
    connection: Connection[Row], source_id: str, target_ids: list[UUID]
) -> None:
    if _target_ids(connection, source_id) != target_ids:
        raise DataValidationError(
            "erasure_plan_stale",
            "The dependency graph changed; create and review a new erasure plan.",
        )


def _delete_targets(connection: Connection[Row], source_id: str, ids: list[UUID]) -> None:
    connection.execute(
        """
        DELETE FROM ynoy.derivation_edges
        WHERE source_record_id = ANY(%s::uuid[]) OR derived_record_id = ANY(%s::uuid[])
        """,
        (ids, ids),
    )
    connection.execute(
        """
        DELETE FROM ynoy.memory_corrections
        WHERE target_record_id = ANY(%s::uuid[]) OR replacement_record_id = ANY(%s::uuid[])
        """,
        (ids, ids),
    )
    for table in (
        "identity_candidates",
        "claim_candidates",
        "continuity_events",
        "bootstrap_declarations",
        "bootstrap_sources",
    ):
        connection.execute(f"DELETE FROM ynoy.{table} WHERE record_id = ANY(%s::uuid[])", (ids,))
    connection.execute(
        """
        DELETE FROM ynoy.private_reports
        WHERE record_id = ANY(%s::uuid[]) OR source_record_ids && %s::uuid[]
        """,
        (ids, ids),
    )
    connection.execute("DELETE FROM ynoy.source_events WHERE record_id = ANY(%s::uuid[])", (ids,))
    connection.execute("DELETE FROM ynoy.source_receipts WHERE source_id = %s", (source_id,))
    connection.execute(
        "DELETE FROM ynoy.inventory_manifests WHERE source_archive_sha256 = %s", (source_id,)
    )


def _append_tombstone(connection: Connection[Row], plan_id: UUID, count: int) -> None:
    receipt = AuditReceipt(
        event_type="erasure_confirm",
        actor_class="represented_user",
        config_version=SCHEMA_VERSION,
        opaque_input_ids=(str(plan_id),),
        input_count=count,
        decision="complete",
        reason_code="local_dependency_cascade_deleted",
        status="success",
    )
    insert_audit_receipt(connection, receipt)


def _append_database_delete_receipt(connection: Connection[Row], plan_id: UUID, count: int) -> None:
    receipt = AuditReceipt(
        event_type="erasure_confirm",
        actor_class="represented_user",
        config_version=SCHEMA_VERSION,
        opaque_input_ids=(str(plan_id),),
        input_count=count,
        decision="partial",
        reason_code="local_database_deleted_pending_artifact_cleanup",
        status="partial",
    )
    insert_audit_receipt(connection, receipt)


def _append_erasure_plan_receipt(connection: Connection[Row], plan_id: UUID, count: int) -> None:
    receipt = AuditReceipt(
        event_type="erasure_plan",
        actor_class="represented_user",
        config_version=SCHEMA_VERSION,
        opaque_input_ids=(str(plan_id),),
        input_count=count,
        decision="allow",
        reason_code="dependency_erasure_plan_created",
        status="success",
    )
    insert_audit_receipt(connection, receipt)
