from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime

from ynoy.direct_memory.codec import strict_dumps, strict_loads
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import SourceType, ToolReceipt
from ynoy.direct_memory.source_events import assert_new_source_id, trusted_time
from ynoy.errors import DataValidationError
from ynoy.models import Speaker
from ynoy.util import canonical_sha256, sha256_text


class ToolResultOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock

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
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id != source_id.strip()
        ):
            raise DataValidationError(
                "direct_memory_source_invalid",
                "Tool source identifier must be non-empty and trimmed.",
            )
        if not isinstance(project, str) or not project or project != project.strip():
            raise DataValidationError(
                "direct_memory_project_invalid",
                "Tool project identifier must be non-empty and trimmed.",
            )
        input_json = strict_dumps(inputs)
        result_json = strict_dumps(result)
        result_value = strict_loads(result_json)
        if not isinstance(result_value, dict):
            raise DataValidationError(
                "direct_memory_tool_result_invalid", "Tool result must be a JSON object."
            )
        with self.database.mutation(project, expected_revision) as (connection, revision):
            recorded_at = trusted_time(self.clock)
            assert_new_source_id(connection, source_id)
            self._insert_source(connection, source_id, project, result_json, recorded_at, revision)
            receipt = ToolReceipt(
                tool_receipt_id=source_id,
                project=project,
                tool_name=tool_name,
                operation=operation,
                input_sha256=canonical_sha256(strict_loads(input_json)),
                result=result_value,
                result_sha256=canonical_sha256(result_value),
                recorded_at=recorded_at,
                revision=revision,
            )
            self._insert_receipt(connection, receipt, result_json)
        return receipt

    @staticmethod
    def _insert_source(
        connection: sqlite3.Connection,
        source_id: str,
        project: str,
        result_json: str,
        recorded_at: datetime,
        revision: int,
    ) -> None:
        connection.execute(
            "INSERT INTO source_events VALUES(?,?,?,?,?,?,?,?,?)",
            (
                source_id,
                project,
                Speaker.TOOL.value,
                None,
                recorded_at.isoformat(),
                result_json,
                sha256_text(result_json),
                SourceType.TOOL_RESULT.value,
                revision,
            ),
        )

    @staticmethod
    def _insert_receipt(
        connection: sqlite3.Connection, receipt: ToolReceipt, result_json: str
    ) -> None:
        connection.execute(
            "INSERT INTO tool_receipts VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                receipt.tool_receipt_id,
                receipt.tool_receipt_id,
                receipt.project,
                receipt.tool_name,
                receipt.operation,
                receipt.input_sha256,
                result_json,
                receipt.result_sha256,
                receipt.recorded_at.isoformat(),
                receipt.revision,
            ),
        )


__all__ = ["ToolResultOperations"]
