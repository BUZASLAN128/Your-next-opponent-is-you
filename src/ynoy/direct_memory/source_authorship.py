from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime

from ynoy.direct_memory.codec import source_authorship_payload_sha256, strict_dumps, strict_loads
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import SourceEvent, SourceType, UserAuthorizationReceipt
from ynoy.direct_memory.source_events import trusted_time
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError
from ynoy.models import Speaker


class SourceAuthorshipOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock
        self.sources = SourceOperations(database, clock)

    def attribute_source_authorship(
        self,
        source_id: str,
        authorization: UserAuthorizationReceipt,
        *,
        expected_revision: int,
    ) -> int:
        event = self.sources.get_source_event(source_id)
        _require_imported_user(event)
        _verify_attribution(self.sources, event, authorization)
        auth_json = strict_dumps(authorization.model_dump(mode="json"))
        with self.database.mutation(event.project, expected_revision) as (connection, revision):
            self._store_attribution(
                connection, event, source_id, auth_json, authorization, revision
            )
        return revision

    def require_reviewable_source(self, event: SourceEvent, subject_id: str) -> None:
        if event.speaker != Speaker.USER:
            raise DataValidationError(
                "direct_memory_review_source_speaker",
                "YNOY interaction review requires an explicitly user-authored source.",
            )
        if event.source_type == SourceType.LIVE_USER_INPUT:
            self._require_live_subject(event, subject_id)
            return
        if event.source_type != SourceType.IMPORTED:
            raise DataValidationError(
                "direct_memory_review_source_type",
                "Tool and imported records cannot authorize a review.",
            )
        self._require_imported_attribution(event, subject_id)

    def _store_attribution(
        self,
        connection: sqlite3.Connection,
        event: SourceEvent,
        source_id: str,
        auth_json: str,
        authorization: UserAuthorizationReceipt,
        revision: int,
    ) -> None:
        existing = connection.execute(
            "SELECT 1 FROM source_attributions WHERE source_id=?", (source_id,)
        ).fetchone()
        if existing:
            raise DataValidationError(
                "direct_memory_attribution_exists", "Source authorship attribution is immutable."
            )
        recorded_at = trusted_time(self.clock)
        self.sources.consume_authorization(
            connection,
            authorization,
            project=event.project,
            revision=revision,
            recorded_at=recorded_at,
        )
        connection.execute(
            "INSERT INTO source_attributions VALUES(?,?,?,?,?)",
            (source_id, event.project, auth_json, recorded_at.isoformat(), revision),
        )

    def _require_live_subject(self, event: SourceEvent, subject_id: str) -> None:
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT subject_id FROM live_inputs WHERE source_id=?", (event.source_id,)
            ).fetchone()
        if row is None or row["subject_id"] != subject_id:
            raise DataValidationError(
                "direct_memory_subject_mismatch", "Live user event belongs to another subject."
            )

    def _require_imported_attribution(self, event: SourceEvent, subject_id: str) -> None:
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT authorization_json FROM source_attributions WHERE source_id=?",
                (event.source_id,),
            ).fetchone()
        if row is None:
            raise DataValidationError(
                "direct_memory_attribution_required",
                "Imported user-speaker evidence requires a separate current-user authorship "
                "receipt.",
            )
        try:
            authorization = UserAuthorizationReceipt.model_validate(
                strict_loads(row["authorization_json"])
            )
            if authorization.subject_id != subject_id:
                raise ValueError("source attribution subject mismatch")
            live_event = self.sources.verify_authorization(
                authorization,
                action="source_authorship",
                payload_sha256=source_authorship_payload_sha256(
                    event.source_id, event.sha256, subject_id
                ),
                subject_id=subject_id,
                review_sha256=None,
                allow_consumed=True,
            )
            if live_event.project != event.project:
                raise ValueError("source attribution project mismatch")
        except Exception as exc:
            raise DataValidationError(
                "direct_memory_attribution_integrity",
                "Stored source attribution failed verification.",
            ) from exc


def _require_imported_user(event: SourceEvent) -> None:
    if event.source_type != SourceType.IMPORTED or event.speaker != Speaker.USER:
        raise DataValidationError(
            "direct_memory_attribution_denied",
            "Only imported user-speaker events can receive explicit user authorship attribution.",
        )


def _verify_attribution(
    sources: SourceOperations,
    event: SourceEvent,
    authorization: UserAuthorizationReceipt,
) -> None:
    payload_sha = source_authorship_payload_sha256(
        event.source_id, event.sha256, authorization.subject_id
    )
    live_event = sources.verify_authorization(
        authorization,
        action="source_authorship",
        payload_sha256=payload_sha,
        subject_id=authorization.subject_id,
        review_sha256=None,
    )
    if live_event.project != event.project:
        raise DataValidationError(
            "direct_memory_authorization_mismatch",
            "Source attribution authorization belongs to another project.",
        )


__all__ = ["SourceAuthorshipOperations"]
