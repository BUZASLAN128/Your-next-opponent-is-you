from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import datetime

from pydantic import BaseModel

from ynoy.direct_memory.claims import ClaimOperations
from ynoy.direct_memory.codec import (
    source_authorship_payload_sha256,
    strict_dumps,
    strict_loads,
)
from ynoy.direct_memory.corrections import CorrectionOperations
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import AuthorizationIntent, SourceType, UserAuthorizationReceipt
from ynoy.direct_memory.reviews import ReviewOperations
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError


class ExportOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.sources = SourceOperations(database, clock)
        self.reviews = ReviewOperations(database, clock)
        self.corrections = CorrectionOperations(database, clock)
        self.claims = ClaimOperations(database, clock)

    def export_jsonl(self, project: str | None = None) -> str:
        if project is not None and (not project or project != project.strip()):
            raise DataValidationError(
                "direct_memory_project_invalid", "Project must be non-empty and trimmed."
            )
        projects = self._projects(project)
        entries = []
        for name in projects:
            entries.extend(self._export_project(name))
        entries.sort(
            key=lambda item: (item["project"], item["revision"], item["record_type"], item["id"])
        )
        return "\n".join(strict_dumps(item) for item in entries)

    def _projects(self, project: str | None) -> tuple[str, ...]:
        if project is not None:
            return (project,)
        with closing(self.database.connect()) as connection:
            rows = connection.execute("SELECT project FROM projects ORDER BY project").fetchall()
        return tuple(str(row["project"]) for row in rows)

    def _export_project(self, project: str) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        with closing(self.database.connect()) as connection:
            sources = connection.execute(
                "SELECT * FROM source_events WHERE project=? ORDER BY revision", (project,)
            ).fetchall()
        for row in sources:
            event = self.sources.get_source_event(str(row["source_id"]))
            entries.append(
                _entry(
                    "source_event", project, event.revision, event.source_id, event,
                    data_plane=self.database.data_plane,
                )
            )
            self._export_live_input(event.source_id, project, event.revision, entries)
            self._export_tool_receipt(event.source_id, project, event.revision, entries)
            self._export_attribution(event.source_id, project, entries)
        self._export_reviews(project, entries)
        self._export_authorization_uses(project, entries)
        for revision in self.claims.list_claim_revisions(project):
            entries.append(
                _entry(
                    "claim_revision", project, revision.revision, revision.revision_id, revision,
                    data_plane=self.database.data_plane,
                )
            )
        return entries

    def _export_authorization_uses(self, project: str, entries: list[dict[str, object]]) -> None:
        with closing(self.database.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM authorization_uses WHERE project=? ORDER BY revision", (project,)
            ).fetchall()
        for row in rows:
            event = self.sources.get_source_event(row["live_user_source_id"])
            if event.source_type != SourceType.LIVE_USER_INPUT or event.project != project:
                raise DataValidationError(
                    "direct_memory_authorization_integrity",
                    "Stored authorization use does not bind a live project input.",
                )
            record = {
                "live_user_source_id": row["live_user_source_id"],
                "authorization_sha256": row["authorization_sha256"],
                "project": row["project"],
                "action": row["action"],
                "recorded_at": row["recorded_at"],
                "revision": int(row["revision"]),
            }
            entries.append(
                _entry(
                    "authorization_use",
                    project,
                    int(row["revision"]),
                    row["live_user_source_id"],
                    record,
                    data_plane=self.database.data_plane,
                )
            )

    def _export_live_input(
        self, source_id: str, project: str, revision: int, entries: list[dict[str, object]]
    ) -> None:
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT subject_id,intent_json FROM live_inputs WHERE source_id=?", (source_id,)
            ).fetchone()
        if row is None:
            return
        intent = (
            AuthorizationIntent.model_validate(strict_loads(row["intent_json"]))
            if row["intent_json"]
            else None
        )
        value = {"source_id": source_id, "subject_id": row["subject_id"], "intent": intent}
        entries.append(
            _entry(
                "live_input", project, revision, source_id, value,
                data_plane=self.database.data_plane,
            )
        )

    def _export_tool_receipt(
        self, source_id: str, project: str, revision: int, entries: list[dict[str, object]]
    ) -> None:
        receipt = self.claims._tool_receipt(source_id)
        if receipt is not None:
            entries.append(
                _entry(
                    "tool_receipt", project, revision, source_id, receipt,
                    data_plane=self.database.data_plane,
                )
            )

    def _export_attribution(
        self, source_id: str, project: str, entries: list[dict[str, object]]
    ) -> None:
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM source_attributions WHERE source_id=?", (source_id,)
            ).fetchone()
        if row is None:
            return
        event = self.sources.get_source_event(source_id)
        authorization = UserAuthorizationReceipt.model_validate(
            strict_loads(row["authorization_json"])
        )
        self.sources.verify_authorization(
            authorization,
            action="source_authorship",
            payload_sha256=source_authorship_payload_sha256(
                source_id, event.sha256, authorization.subject_id
            ),
            subject_id=authorization.subject_id,
            review_sha256=None,
            allow_consumed=True,
        )
        if row["project"] != project or event.project != project:
            raise DataValidationError(
                "direct_memory_attribution_integrity", "Stored source attribution project mismatch."
            )
        value = {
            "source_id": source_id,
            "project": project,
            "authorization": authorization,
            "recorded_at": row["recorded_at"],
            "revision": int(row["revision"]),
        }
        entries.append(
            _entry(
                "source_attribution", project, int(row["revision"]), source_id, value,
                data_plane=self.database.data_plane,
            )
        )

    def _export_reviews(self, project: str, entries: list[dict[str, object]]) -> None:
        with closing(self.database.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM reviews WHERE project=? ORDER BY revision", (project,)
            ).fetchall()
        for row in rows:
            stored = self.reviews.get_review(str(row["review_id"]))
            value = {
                "review": stored.review,
                "review_sha256": stored.review_sha256,
                "review_id": stored.review_id,
                "source_id": stored.source_id,
                "facts": self.reviews.review_facts(stored.review_id),
                "recorded_at": row["recorded_at"],
                "revision": stored.revision,
            }
            entries.append(
                _entry(
                    "review", project, stored.revision, stored.review_id, value,
                    data_plane=self.database.data_plane,
                )
            )
            for correction in self.corrections.list_corrections(stored.review_id):
                entries.append(
                    _entry(
                        "correction",
                        project,
                        correction.revision,
                        str(correction.correction.record_id),
                        correction,
                        data_plane=self.database.data_plane,
                    )
                )


def _entry(
    record_type: str,
    project: str,
    revision: int,
    record_id: str,
    value: object,
    *,
    data_plane: DataPlane,
) -> dict[str, object]:
    return {
        "record_type": record_type,
        "data_plane": data_plane.value,
        "project": project,
        "revision": revision,
        "id": record_id,
        "record": _jsonable(value),
    }


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    return value


__all__ = ["ExportOperations"]
