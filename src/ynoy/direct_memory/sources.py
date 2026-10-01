from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime

from ynoy.direct_memory.authorization import AuthorizationOperations
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import SourceEvent, ToolReceipt, UserAuthorizationReceipt
from ynoy.direct_memory.source_events import SourceEventOperations


class SourceOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock
        self.events = SourceEventOperations(database, clock)
        self.auth = AuthorizationOperations(database, clock)

    def current_revision(self, project: str) -> int:
        return self.events.current_revision(project)

    def record_source_event(self, **fields: object) -> SourceEvent:
        return self.events.record_source_event(**fields)  # type: ignore[arg-type]

    def record_live_user_input(self, **fields: object) -> SourceEvent:
        return self.events.record_live_user_input(**fields)  # type: ignore[arg-type]

    def record_tool_result(self, **fields: object) -> ToolReceipt:
        return self.events.record_tool_result(**fields)  # type: ignore[arg-type]

    def get_source_event(self, source_id: str) -> SourceEvent:
        return self.events.get_source_event(source_id)

    def authorize_action(
        self, live_user_source_id: str, **fields: object
    ) -> UserAuthorizationReceipt:
        return self.auth.authorize_action(live_user_source_id, **fields)  # type: ignore[arg-type]

    def verify_authorization(
        self, authorization: UserAuthorizationReceipt, **fields: object
    ) -> SourceEvent:
        return self.auth.verify_authorization(authorization, **fields)  # type: ignore[arg-type]

    @staticmethod
    def consume_authorization(
        connection: sqlite3.Connection,
        authorization: UserAuthorizationReceipt,
        **fields: object,
    ) -> None:
        AuthorizationOperations.consume_authorization(
            connection,
            authorization,
            **fields,  # type: ignore[arg-type]
        )


__all__ = ["SourceOperations"]
