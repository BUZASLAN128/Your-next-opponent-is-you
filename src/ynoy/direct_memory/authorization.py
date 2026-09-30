from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime

from ynoy.direct_memory.codec import strict_loads
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import (
    AuthorizationIntent,
    SourceEvent,
    SourceType,
    UserAuthorizationReceipt,
)
from ynoy.direct_memory.source_events import SourceEventOperations, trusted_time
from ynoy.errors import DataValidationError
from ynoy.util import canonical_sha256


class AuthorizationOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock
        self.events = SourceEventOperations(database, clock)

    def authorize_action(
        self,
        live_user_source_id: str,
        *,
        action: str,
        payload_sha256: str,
        subject_id: str,
        review_sha256: str | None = None,
    ) -> UserAuthorizationReceipt:
        event = self.events.get_source_event(live_user_source_id)
        if event.source_type != SourceType.LIVE_USER_INPUT:
            raise _required("Only a dedicated live user input can authorize an action.")
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT subject_id,intent_json FROM live_inputs WHERE source_id=?",
                (live_user_source_id,),
            ).fetchone()
            used = connection.execute(
                "SELECT 1 FROM authorization_uses WHERE live_user_source_id=?",
                (live_user_source_id,),
            ).fetchone()
        if row is None or row["intent_json"] is None or used is not None:
            raise _required("Live input has no unused authorization intent.")
        intent = AuthorizationIntent.model_validate(strict_loads(row["intent_json"]))
        if (action, payload_sha256, subject_id, review_sha256) != (
            intent.action,
            intent.payload_sha256,
            intent.subject_id,
            intent.review_sha256,
        ) or intent.subject_id != row["subject_id"]:
            raise DataValidationError(
                "direct_memory_authorization_mismatch",
                "Live authorization does not match its declared action and payload.",
            )
        draft = UserAuthorizationReceipt.model_construct(
            action=action,
            payload_sha256=payload_sha256,
            subject_id=subject_id,
            review_sha256=review_sha256,
            live_user_source_id=event.source_id,
            live_user_source_sha256=event.sha256,
            authorized_at=trusted_time(self.clock),
            authorization_sha256="0" * 64,
        )
        payload = draft.model_dump(mode="python")
        payload["authorization_sha256"] = canonical_sha256(
            draft.model_dump(mode="json", exclude={"authorization_sha256"})
        )
        return UserAuthorizationReceipt.model_validate(payload)

    def verify_authorization(
        self,
        authorization: UserAuthorizationReceipt,
        *,
        action: str,
        payload_sha256: str,
        subject_id: str,
        review_sha256: str | None,
        allow_consumed: bool = False,
    ) -> SourceEvent:
        safe = _validated_receipt(authorization)
        supplied = (action, payload_sha256, subject_id, review_sha256)
        received = (safe.action, safe.payload_sha256, safe.subject_id, safe.review_sha256)
        if supplied != received:
            raise DataValidationError(
                "direct_memory_authorization_mismatch",
                "Authorization receipt does not bind this exact operation.",
            )
        event = self.events.get_source_event(safe.live_user_source_id)
        if (
            event.source_type != SourceType.LIVE_USER_INPUT
            or event.sha256 != safe.live_user_source_sha256
        ):
            raise _required("Authorization source is not a matching live user input.")
        _verify_live_intent(self.database, event, safe, supplied, allow_consumed)
        return event

    @staticmethod
    def consume_authorization(
        connection: sqlite3.Connection,
        authorization: UserAuthorizationReceipt,
        *,
        project: str,
        revision: int,
        recorded_at: datetime,
    ) -> None:
        try:
            connection.execute(
                "INSERT INTO authorization_uses VALUES(?,?,?,?,?,?)",
                (
                    authorization.live_user_source_id,
                    authorization.authorization_sha256,
                    project,
                    authorization.action,
                    recorded_at.isoformat(),
                    revision,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DataValidationError(
                "direct_memory_authorization_replayed",
                "A live authorization receipt can be consumed only once.",
            ) from exc


def _validated_receipt(value: UserAuthorizationReceipt) -> UserAuthorizationReceipt:
    try:
        return UserAuthorizationReceipt.model_validate(value.model_dump(mode="python"))
    except Exception as exc:
        raise _required("Authorization receipt failed its integrity check.") from exc


def _verify_live_intent(
    database: DirectMemoryDatabase,
    event: SourceEvent,
    authorization: UserAuthorizationReceipt,
    supplied: tuple[str, str, str, str | None],
    allow_consumed: bool,
) -> None:
    with closing(database.connect()) as connection:
        row = connection.execute(
            "SELECT subject_id,intent_json FROM live_inputs WHERE source_id=?", (event.source_id,)
        ).fetchone()
        used = connection.execute(
            "SELECT authorization_sha256,project,action FROM authorization_uses "
            "WHERE live_user_source_id=?",
            (event.source_id,),
        ).fetchone()
    if row is None or row["intent_json"] is None:
        raise _required("Live input did not declare an authorization intent.")
    intent = AuthorizationIntent.model_validate(strict_loads(row["intent_json"]))
    declared = (intent.action, intent.payload_sha256, intent.subject_id, intent.review_sha256)
    if supplied != declared:
        raise DataValidationError(
            "direct_memory_authorization_mismatch",
            "Authorization does not match the intent recorded with live input.",
        )
    if intent.subject_id != row["subject_id"] or (used is not None and not allow_consumed):
        raise _required("Authorization subject is wrong or live input was already consumed.")
    if allow_consumed and not _use_matches(used, event, authorization):
        raise _required("Authorization use receipt does not match the stored operation.")


def _use_matches(
    used: sqlite3.Row | None,
    event: SourceEvent,
    authorization: UserAuthorizationReceipt,
) -> bool:
    return (
        used is not None
        and used["authorization_sha256"] == authorization.authorization_sha256
        and used["project"] == event.project
        and used["action"] == authorization.action
    )


def _required(message: str) -> DataValidationError:
    return DataValidationError("direct_memory_authorization_required", message)
