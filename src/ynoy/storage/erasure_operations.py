from __future__ import annotations

from uuid import UUID

from psycopg import Connection

from ynoy.errors import DataValidationError
from ynoy.storage.database import Row, require_row

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


def target_ids(connection: Connection[Row], source_id: str) -> list[UUID]:
    rows = connection.execute(TARGETS_SQL, (source_id,)).fetchall()
    return [row["record_id"] for row in rows]


def target_counts(
    connection: Connection[Row], source_id: str, record_ids: list[UUID]
) -> dict[str, int]:
    counts = {
        table: _count_any(connection, table, "record_id", record_ids)
        for table in (
            "source_events",
            "inventory_manifests",
            "ingestion_approvals",
            "bootstrap_sources",
            "bootstrap_declarations",
            "claim_candidates",
            "identity_candidates",
        )
    }
    counts["continuity_events"] = _continuity_count(connection, record_ids)
    for table in ("decision_events", "control_records"):
        counts[table] = _count_any(connection, table, "source_event_id", record_ids)
    counts["source_receipts"] = _source_receipt_count(connection, source_id)
    counts["private_reports"] = _report_count(connection, record_ids)
    return counts


def assert_current_targets(
    connection: Connection[Row], source_id: str, record_ids: list[UUID]
) -> None:
    if target_ids(connection, source_id) != record_ids:
        raise DataValidationError(
            "erasure_plan_stale",
            "The dependency graph changed; create and review a new erasure plan.",
        )


def delete_targets(connection: Connection[Row], source_id: str, record_ids: list[UUID]) -> None:
    connection.execute(
        """
        DELETE FROM ynoy.derivation_edges
        WHERE source_record_id = ANY(%s::uuid[]) OR derived_record_id = ANY(%s::uuid[])
        """,
        (record_ids, record_ids),
    )
    connection.execute(
        """
        DELETE FROM ynoy.memory_corrections
        WHERE target_record_id = ANY(%s::uuid[]) OR replacement_record_id = ANY(%s::uuid[])
        """,
        (record_ids, record_ids),
    )
    _delete_primary_records(connection, record_ids)
    connection.execute(
        """
        DELETE FROM ynoy.private_reports
        WHERE record_id = ANY(%s::uuid[]) OR source_record_ids && %s::uuid[]
        """,
        (record_ids, record_ids),
    )
    connection.execute(
        "DELETE FROM ynoy.source_events WHERE record_id = ANY(%s::uuid[])", (record_ids,)
    )
    connection.execute("DELETE FROM ynoy.source_receipts WHERE source_id = %s", (source_id,))
    connection.execute(
        "DELETE FROM ynoy.inventory_manifests WHERE source_archive_sha256 = %s", (source_id,)
    )


def _delete_primary_records(connection: Connection[Row], record_ids: list[UUID]) -> None:
    for table in (
        "identity_candidates",
        "claim_candidates",
        "bootstrap_declarations",
        "bootstrap_sources",
    ):
        connection.execute(
            f"DELETE FROM ynoy.{table} WHERE record_id = ANY(%s::uuid[])", (record_ids,)
        )
    connection.execute(
        """
        DELETE FROM ynoy.continuity_events
        WHERE record_id = ANY(%s::uuid[])
           OR earlier_record_id = ANY(%s::uuid[])
           OR later_record_id = ANY(%s::uuid[])
        """,
        (record_ids, record_ids, record_ids),
    )


def _count_any(connection: Connection[Row], table: str, column: str, record_ids: list[UUID]) -> int:
    row = connection.execute(
        f"SELECT count(*) AS count FROM ynoy.{table} WHERE {column} = ANY(%s::uuid[])",
        (record_ids,),
    ).fetchone()
    return int(require_row(row, f"{table} erasure count")["count"])


def _source_receipt_count(connection: Connection[Row], source_id: str) -> int:
    row = connection.execute(
        "SELECT count(*) AS count FROM ynoy.source_receipts WHERE source_id = %s", (source_id,)
    ).fetchone()
    return int(require_row(row, "source receipt erasure count")["count"])


def _report_count(connection: Connection[Row], record_ids: list[UUID]) -> int:
    row = connection.execute(
        """
        SELECT count(*) AS count FROM ynoy.private_reports
        WHERE record_id = ANY(%s::uuid[]) OR source_record_ids && %s::uuid[]
        """,
        (record_ids, record_ids),
    ).fetchone()
    return int(require_row(row, "private report erasure count")["count"])


def _continuity_count(connection: Connection[Row], record_ids: list[UUID]) -> int:
    row = connection.execute(
        """
        SELECT count(*) AS count FROM ynoy.continuity_events
        WHERE record_id = ANY(%s::uuid[])
           OR earlier_record_id = ANY(%s::uuid[])
           OR later_record_id = ANY(%s::uuid[])
        """,
        (record_ids, record_ids, record_ids),
    ).fetchone()
    return int(require_row(row, "continuity event erasure count")["count"])
