from __future__ import annotations

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.errors import DataValidationError
from ynoy.models import NormalizedCodexEvent
from ynoy.storage.database import Row


def insert_normalized_event(connection: Connection[Row], event: NormalizedCodexEvent) -> None:
    inserted = connection.execute(
        """
        INSERT INTO ynoy.codex_normalized_events (
            record_id, snapshot_id, source_key, blob_sha256, byte_start,
            byte_length, line_number, record_sha256, record_type, payload_type,
            actor_origin, structural_role, claim_holder, source_authority, status,
            content, content_sha256, event_time, conversation_key, turn_key,
            duplicate_of, exclusion_reason, safe_action_metadata, data_class,
            synthetic, parser_version, event_sha256, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (record_id) DO NOTHING
        """,
        _event_values(event),
    ).rowcount
    if inserted:
        return
    row = connection.execute(
        "SELECT event_sha256 FROM ynoy.codex_normalized_events WHERE record_id = %s",
        (event.record_id,),
    ).fetchone()
    if row is None or row["event_sha256"] != event.event_sha256:
        raise DataValidationError(
            "codex_ingest_event_conflict",
            "Normalized event identifier already binds different content.",
        )


def _event_values(event: NormalizedCodexEvent) -> tuple[object, ...]:
    return (
        event.record_id,
        event.snapshot_id,
        event.source_key,
        event.blob_sha256,
        event.byte_start,
        event.byte_length,
        event.line_number,
        event.record_sha256,
        event.record_type,
        event.payload_type,
        event.actor_origin.value,
        event.structural_role.value,
        event.claim_holder.value,
        event.source_authority.value,
        event.status,
        event.content,
        event.content_sha256,
        event.event_time,
        event.conversation_key,
        event.turn_key,
        event.duplicate_of,
        event.exclusion_reason,
        Jsonb(event.safe_action_metadata),
        event.data_class.value,
        event.synthetic,
        event.parser_version,
        event.event_sha256,
        event.created_at,
    )
