from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.constants import CODEX_INGEST_TRANSACTION_EVENTS, CODEX_INGEST_VERSION
from ynoy.errors import DataValidationError
from ynoy.models import AuditReceipt, CodexIngestionReceipt, NormalizedCodexEvent
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database, Row
from ynoy.storage.ingestion_event_writes import insert_normalized_event
from ynoy.util import utc_now


@dataclass(frozen=True, slots=True)
class IngestionCheckpoint:
    snapshot_id: UUID
    source_key: str
    blob_sha256: str
    expected_bytes: int
    next_byte_offset: int
    completed_lines: int
    parser_state: dict[str, object]
    event_count: int
    dialogue_count: int
    safe_action_count: int
    quarantined_count: int
    status: str


class CodexIngestionRepository:
    def __init__(self, database: Database):
        self.database = database

    def prepare(self, snapshot_id: UUID) -> tuple[IngestionCheckpoint, ...]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT source_key, blob_sha256, expected_bytes
                FROM ynoy.corpus_snapshot_files
                WHERE snapshot_id = %s AND status = 'vaulted'
                ORDER BY source_key
                """,
                (snapshot_id,),
            ).fetchall()
            for row in rows:
                _insert_checkpoint(connection, snapshot_id, row)
            checkpoints = _load_checkpoints(connection, snapshot_id)
        return checkpoints

    def load(self, snapshot_id: UUID, source_key: str) -> IngestionCheckpoint:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM ynoy.codex_ingestion_checkpoints
                WHERE snapshot_id = %s AND source_key = %s
                """,
                (snapshot_id, source_key),
            ).fetchone()
        if row is None:
            raise DataValidationError(
                "codex_ingest_checkpoint_missing", "Codex ingestion checkpoint is missing."
            )
        return _checkpoint(row)

    def save_batch(
        self,
        checkpoint: IngestionCheckpoint,
        events: list[NormalizedCodexEvent],
        parser_state: dict[str, object],
    ) -> IngestionCheckpoint:
        _validate_batch(checkpoint, events)
        with self.database.connect() as connection:
            locked = _lock_checkpoint(connection, checkpoint)
            for event in events:
                insert_normalized_event(connection, event)
            _advance_checkpoint(connection, locked, events, parser_state)
            current = _load_checkpoint(connection, locked.snapshot_id, locked.source_key)
        return current

    def summary(self, snapshot_id: UUID) -> dict[str, object]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    count(*) AS file_count,
                    count(*) FILTER (WHERE status = 'complete') AS complete_files,
                    COALESCE(sum(next_byte_offset), 0) AS processed_bytes,
                    COALESCE(sum(event_count), 0) AS event_count,
                    COALESCE(sum(dialogue_count), 0) AS dialogue_count,
                    COALESCE(sum(safe_action_count), 0) AS safe_action_count,
                    COALESCE(sum(quarantined_count), 0) AS quarantined_count
                FROM ynoy.codex_ingestion_checkpoints WHERE snapshot_id = %s
                """,
                (snapshot_id,),
            ).fetchone()
        assert row is not None
        return dict(row)

    def save_receipt(self, receipt: CodexIngestionReceipt, audit: AuditReceipt) -> bool:
        safe = CodexIngestionReceipt.model_validate(receipt.model_dump(mode="python"))
        with self.database.connect() as connection:
            inserted = connection.execute(
                """
                INSERT INTO ynoy.codex_ingestion_receipts (
                    record_id, snapshot_id, snapshot_receipt_sha256,
                    receipt_sha256, status, record, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO NOTHING
                """,
                (
                    safe.record_id,
                    safe.snapshot_id,
                    safe.snapshot_receipt_sha256,
                    safe.receipt_sha256,
                    safe.status,
                    Jsonb(safe.model_dump(mode="json")),
                    safe.created_at,
                ),
            ).rowcount
            if inserted:
                insert_audit_receipt(connection, audit)
        return bool(inserted)


def _insert_checkpoint(connection: Connection[Row], snapshot_id: UUID, row: Row) -> None:
    expected = int(row["expected_bytes"])
    connection.execute(
        """
        INSERT INTO ynoy.codex_ingestion_checkpoints (
            snapshot_id, source_key, blob_sha256, expected_bytes, status,
            parser_version, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_id, source_key) DO NOTHING
        """,
        (
            snapshot_id,
            row["source_key"],
            row["blob_sha256"],
            expected,
            "complete" if expected == 0 else "pending",
            CODEX_INGEST_VERSION,
            utc_now(),
        ),
    )


def _load_checkpoints(
    connection: Connection[Row], snapshot_id: UUID
) -> tuple[IngestionCheckpoint, ...]:
    rows = connection.execute(
        """
        SELECT * FROM ynoy.codex_ingestion_checkpoints
        WHERE snapshot_id = %s ORDER BY source_key
        """,
        (snapshot_id,),
    ).fetchall()
    return tuple(_checkpoint(row) for row in rows)


def _load_checkpoint(
    connection: Connection[Row], snapshot_id: UUID, source_key: str
) -> IngestionCheckpoint:
    row = connection.execute(
        """
        SELECT * FROM ynoy.codex_ingestion_checkpoints
        WHERE snapshot_id = %s AND source_key = %s
        """,
        (snapshot_id, source_key),
    ).fetchone()
    if row is None:
        raise DataValidationError(
            "codex_ingest_checkpoint_missing", "Codex ingestion checkpoint is missing."
        )
    return _checkpoint(row)


def _lock_checkpoint(
    connection: Connection[Row], expected: IngestionCheckpoint
) -> IngestionCheckpoint:
    row = connection.execute(
        """
        SELECT * FROM ynoy.codex_ingestion_checkpoints
        WHERE snapshot_id = %s AND source_key = %s FOR UPDATE
        """,
        (expected.snapshot_id, expected.source_key),
    ).fetchone()
    current = _checkpoint(row) if row is not None else None
    if current is None or current.next_byte_offset != expected.next_byte_offset:
        raise DataValidationError(
            "codex_ingest_checkpoint_stale", "Codex ingestion checkpoint is stale."
        )
    return current


def _advance_checkpoint(
    connection: Connection[Row],
    checkpoint: IngestionCheckpoint,
    events: list[NormalizedCodexEvent],
    parser_state: dict[str, object],
) -> None:
    if not events:
        return
    next_offset = events[-1].byte_start + events[-1].byte_length
    counts = {status: sum(event.status == status for event in events) for status in _STATUSES}
    connection.execute(
        """
        UPDATE ynoy.codex_ingestion_checkpoints SET
            next_byte_offset = %s, completed_lines = %s, parser_state = %s,
            event_count = event_count + %s, dialogue_count = dialogue_count + %s,
            safe_action_count = safe_action_count + %s,
            quarantined_count = quarantined_count + %s, status = %s, updated_at = %s
        WHERE snapshot_id = %s AND source_key = %s
        """,
        (
            next_offset,
            events[-1].line_number,
            Jsonb(parser_state),
            len(events),
            counts["dialogue"],
            counts["safe_action"],
            counts["quarantined"],
            "complete" if next_offset == checkpoint.expected_bytes else "in_progress",
            utc_now(),
            checkpoint.snapshot_id,
            checkpoint.source_key,
        ),
    )


_STATUSES = ("dialogue", "safe_action", "quarantined")


def _validate_batch(checkpoint: IngestionCheckpoint, events: list[NormalizedCodexEvent]) -> None:
    if not events or len(events) > CODEX_INGEST_TRANSACTION_EVENTS:
        raise DataValidationError(
            "codex_ingest_batch_size_invalid", "Codex ingestion batch size is invalid."
        )
    expected_offset = checkpoint.next_byte_offset
    for event in events:
        if (
            event.snapshot_id != checkpoint.snapshot_id
            or event.source_key != checkpoint.source_key
            or event.blob_sha256 != checkpoint.blob_sha256
            or event.byte_start != expected_offset
        ):
            raise DataValidationError(
                "codex_ingest_batch_disconnected", "Codex ingestion batch is disconnected."
            )
        expected_offset += event.byte_length
    if expected_offset > checkpoint.expected_bytes:
        raise DataValidationError(
            "codex_ingest_batch_overflow", "Codex ingestion batch exceeds the source blob."
        )


def _checkpoint(row: Row) -> IngestionCheckpoint:
    state = row["parser_state"]
    return IngestionCheckpoint(
        snapshot_id=UUID(str(row["snapshot_id"])),
        source_key=str(row["source_key"]),
        blob_sha256=str(row["blob_sha256"]),
        expected_bytes=int(row["expected_bytes"]),
        next_byte_offset=int(row["next_byte_offset"]),
        completed_lines=int(row["completed_lines"]),
        parser_state=dict(state) if isinstance(state, dict) else {},
        event_count=int(row["event_count"]),
        dialogue_count=int(row["dialogue_count"]),
        safe_action_count=int(row["safe_action_count"]),
        quarantined_count=int(row["quarantined_count"]),
        status=str(row["status"]),
    )
