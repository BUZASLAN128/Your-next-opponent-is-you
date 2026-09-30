from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import UTC, datetime

from ynoy.direct_memory.codec import strict_dumps
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import AuthorizationIntent, SourceEvent, SourceType, ToolReceipt
from ynoy.direct_memory.subject_scope import assert_project_subject
from ynoy.errors import DataValidationError
from ynoy.models import Speaker
from ynoy.util import sha256_text


class SourceEventOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock

    def current_revision(self, project: str) -> int:
        return self.database.current_revision(project)

    def record_source_event(
        self,
        *,
        source_id: str,
        project: str,
        speaker: Speaker | str,
        said_at: datetime | None,
        exact_text: str,
        expected_revision: int,
    ) -> SourceEvent:
        return self._record_event(
            source_id=source_id,
            project=project,
            speaker=speaker,
            said_at=said_at,
            exact_text=exact_text,
            source_type=SourceType.IMPORTED,
            expected_revision=expected_revision,
        )

    def record_live_user_input(
        self,
        *,
        source_id: str,
        project: str,
        said_at: datetime | None,
        exact_text: str,
        expected_revision: int,
        authorization_intent: AuthorizationIntent | None = None,
        subject_id: str = "self",
    ) -> SourceEvent:
        if not subject_id or subject_id != subject_id.strip():
            raise DataValidationError(
                "direct_memory_subject_invalid", "Subject id must be trimmed."
            )
        if authorization_intent is not None and authorization_intent.subject_id != subject_id:
            raise DataValidationError(
                "direct_memory_authorization_mismatch", "Intent subject must match live user input."
            )
        intent = (
            strict_dumps(authorization_intent.model_dump(mode="json"))
            if authorization_intent is not None
            else None
        )
        return self._record_event(
            source_id=source_id,
            project=project,
            speaker=Speaker.USER,
            said_at=said_at,
            exact_text=exact_text,
            source_type=SourceType.LIVE_USER_INPUT,
            expected_revision=expected_revision,
            intent_json=intent,
            live_subject_id=subject_id,
        )

    def record_tool_result(
        self,
        *,
        source_id: str,
        project: str,
        tool_name: str,
        operation: str,
        inputs: Mapping[str, object],
        result: Mapping[str, object],
        expected_revision: int,
    ) -> ToolReceipt:
        from ynoy.direct_memory.tool_results import ToolResultOperations

        return ToolResultOperations(self.database, self.clock).record_tool_result(
            source_id=source_id,
            project=project,
            tool_name=tool_name,
            operation=operation,
            inputs=inputs,
            result=result,
            expected_revision=expected_revision,
        )

    def get_source_event(self, source_id: str) -> SourceEvent:
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM source_events WHERE source_id=?", (source_id,)
            ).fetchone()
        if row is None:
            raise DataValidationError(
                "direct_memory_source_missing", "Direct-memory source event does not exist."
            )
        try:
            return SourceEvent.model_validate(dict(row))
        except Exception as exc:
            raise DataValidationError(
                "direct_memory_source_integrity",
                "Stored source event failed hash or schema checks.",
            ) from exc

    def _record_event(
        self,
        *,
        source_id: str,
        project: str,
        speaker: Speaker | str,
        said_at: datetime | None,
        exact_text: str,
        source_type: SourceType,
        expected_revision: int,
        intent_json: str | None = None,
        live_subject_id: str = "self",
    ) -> SourceEvent:
        try:
            safe_speaker = Speaker(speaker)
        except ValueError as exc:
            raise DataValidationError(
                "direct_memory_speaker_invalid", "Unknown source speaker."
            ) from exc
        with self.database.mutation(project, expected_revision) as (connection, revision):
            recorded_at = trusted_time(self.clock)
            assert_new_source_id(connection, source_id)
            if source_type == SourceType.LIVE_USER_INPUT:
                assert_project_subject(connection, project, live_subject_id)
            event = SourceEvent(
                source_id=source_id,
                project=project,
                speaker=safe_speaker,
                said_at=said_at,
                recorded_at=recorded_at,
                exact_text=exact_text,
                sha256=sha256_text(exact_text),
                source_type=source_type,
                revision=revision,
            )
            _insert_event(connection, event, intent_json, live_subject_id)
        return event


def trusted_time(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.utcoffset() is None:
        raise DataValidationError("direct_memory_clock_invalid", "Clock must return an aware time.")
    return value.astimezone(UTC)


def assert_new_source_id(connection: sqlite3.Connection, source_id: str) -> None:
    if connection.execute("SELECT 1 FROM source_events WHERE source_id=?", (source_id,)).fetchone():
        raise DataValidationError(
            "direct_memory_source_exists", "Source identifiers are immutable and unique."
        )


def _insert_event(
    connection: sqlite3.Connection,
    event: SourceEvent,
    intent_json: str | None,
    live_subject_id: str,
) -> None:
    connection.execute(
        "INSERT INTO source_events VALUES(?,?,?,?,?,?,?,?,?)",
        (
            event.source_id,
            event.project,
            event.speaker.value,
            event.said_at.isoformat() if event.said_at else None,
            event.recorded_at.isoformat(),
            event.exact_text,
            event.sha256,
            event.source_type.value,
            event.revision,
        ),
    )
    if event.source_type == SourceType.LIVE_USER_INPUT:
        connection.execute(
            "INSERT INTO live_inputs VALUES(?,?,?)",
            (event.source_id, live_subject_id, intent_json),
        )
