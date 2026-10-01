from __future__ import annotations

import sqlite3

from ynoy.errors import DataValidationError


def assert_project_subject(connection: sqlite3.Connection, project: str, subject_id: str) -> None:
    current = project_subject(connection, project)
    if current is not None and current != subject_id:
        raise DataValidationError(
            "direct_memory_project_subject_mismatch",
            "A direct-memory project can contain live inputs for only one subject.",
        )


def project_subject(
    connection: sqlite3.Connection, project: str, *, revision_cutoff: int | None = None
) -> str | None:
    revision_filter = " AND source_events.revision<=?" if revision_cutoff is not None else ""
    parameters: tuple[object, ...] = (project,)
    if revision_cutoff is not None:
        parameters = (project, revision_cutoff)
    rows = connection.execute(
        "SELECT DISTINCT live_inputs.subject_id FROM live_inputs "
        "JOIN source_events ON source_events.source_id=live_inputs.source_id "
        "WHERE source_events.project=?" + revision_filter + " ORDER BY live_inputs.subject_id",
        parameters,
    ).fetchall()
    subjects = tuple(str(row[0]) for row in rows)
    if len(subjects) > 1 or any(not item or item != item.strip() for item in subjects):
        raise DataValidationError(
            "direct_memory_project_subject_mismatch",
            "Stored live inputs have inconsistent project subjects.",
        )
    return subjects[0] if subjects else None


__all__ = ["assert_project_subject", "project_subject"]
