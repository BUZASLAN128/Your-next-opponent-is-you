from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from ynoy.direct_memory.backup_publish import backup_to_path
from ynoy.direct_memory.schema_checks import (
    assert_schema_identity,
    create_schema,
    schema_object_names,
    table_names,
)
from ynoy.errors import DataValidationError
from ynoy.policy import assert_outside_git

_APPLICATION_ID = 0x594E4D31
_SCHEMA_VERSION = 1
_TABLES = {
    "projects",
    "source_events",
    "live_inputs",
    "authorization_uses",
    "source_attributions",
    "tool_receipts",
    "reviews",
    "corrections",
    "claim_revisions",
}
_DDL = (
    "CREATE TABLE projects (project TEXT PRIMARY KEY, "
    "revision INTEGER NOT NULL CHECK(revision >= 0))",
    """CREATE TABLE source_events (
        source_id TEXT PRIMARY KEY, project TEXT NOT NULL, speaker TEXT NOT NULL,
        said_at TEXT, recorded_at TEXT NOT NULL, exact_text TEXT NOT NULL,
        sha256 TEXT NOT NULL, source_type TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE live_inputs (
        source_id TEXT PRIMARY KEY REFERENCES source_events(source_id),
        subject_id TEXT NOT NULL, intent_json TEXT)""",
    """CREATE TABLE authorization_uses (
        live_user_source_id TEXT PRIMARY KEY REFERENCES source_events(source_id),
        authorization_sha256 TEXT NOT NULL, project TEXT NOT NULL, action TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE source_attributions (
        source_id TEXT PRIMARY KEY REFERENCES source_events(source_id), project TEXT NOT NULL,
        authorization_json TEXT NOT NULL, recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE tool_receipts (
        tool_receipt_id TEXT PRIMARY KEY, source_id TEXT UNIQUE NOT NULL
        REFERENCES source_events(source_id),
        project TEXT NOT NULL, tool_name TEXT NOT NULL, operation TEXT NOT NULL,
        input_sha256 TEXT NOT NULL, result_json TEXT NOT NULL, result_sha256 TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE reviews (
        review_id TEXT PRIMARY KEY, project TEXT NOT NULL, source_id TEXT NOT NULL,
        review_json TEXT NOT NULL, review_sha256 TEXT NOT NULL, facts_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE corrections (
        correction_id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(review_id),
        project TEXT NOT NULL, operation TEXT NOT NULL, correction_json TEXT NOT NULL,
        state_json TEXT NOT NULL, authorization_json TEXT NOT NULL,
        supersessions_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE claim_revisions (
        revision_id TEXT PRIMARY KEY, project TEXT NOT NULL, fact_key TEXT NOT NULL,
        evidence_ids_json TEXT NOT NULL, state TEXT NOT NULL, kind TEXT NOT NULL,
        payload_json TEXT NOT NULL, event_time TEXT, recorded_at TEXT NOT NULL,
        authorization_json TEXT, tool_receipt_id TEXT REFERENCES tool_receipts(tool_receipt_id),
        related_fact_key TEXT, payload_sha256 TEXT NOT NULL, revision INTEGER NOT NULL)""",
    "CREATE INDEX claim_revisions_project_fact ON claim_revisions(project, fact_key, revision)",
    "CREATE INDEX corrections_review_revision ON corrections(review_id, revision)",
)
_IMMUTABLE_TABLES = _TABLES - {"projects"}
_COLUMNS = {
    "projects": ("project", "revision"),
    "source_events": (
        "source_id",
        "project",
        "speaker",
        "said_at",
        "recorded_at",
        "exact_text",
        "sha256",
        "source_type",
        "revision",
    ),
    "live_inputs": ("source_id", "subject_id", "intent_json"),
    "authorization_uses": (
        "live_user_source_id",
        "authorization_sha256",
        "project",
        "action",
        "recorded_at",
        "revision",
    ),
    "source_attributions": (
        "source_id",
        "project",
        "authorization_json",
        "recorded_at",
        "revision",
    ),
    "tool_receipts": (
        "tool_receipt_id",
        "source_id",
        "project",
        "tool_name",
        "operation",
        "input_sha256",
        "result_json",
        "result_sha256",
        "recorded_at",
        "revision",
    ),
    "reviews": (
        "review_id",
        "project",
        "source_id",
        "review_json",
        "review_sha256",
        "facts_json",
        "recorded_at",
        "revision",
    ),
    "corrections": (
        "correction_id",
        "review_id",
        "project",
        "operation",
        "correction_json",
        "state_json",
        "authorization_json",
        "supersessions_json",
        "recorded_at",
        "revision",
    ),
    "claim_revisions": (
        "revision_id",
        "project",
        "fact_key",
        "evidence_ids_json",
        "state",
        "kind",
        "payload_json",
        "event_time",
        "recorded_at",
        "authorization_json",
        "tool_receipt_id",
        "related_fact_key",
        "payload_sha256",
        "revision",
    ),
}


class DirectMemoryDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        assert_outside_git(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_or_validate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            self._assert_database_identity(connection)
            return connection
        except Exception:
            connection.close()
            raise

    def current_revision(self, project: str) -> int:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT revision FROM projects WHERE project=?", (project,)
            ).fetchone()
        return int(row["revision"]) if row else 0

    @contextmanager
    def mutation(
        self, project: str, expected_revision: int
    ) -> Iterator[tuple[sqlite3.Connection, int]]:
        if expected_revision < 0:
            raise DataValidationError(
                "direct_memory_revision_invalid", "Revision cannot be negative."
            )
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_database_identity(connection)
            row = connection.execute(
                "SELECT revision FROM projects WHERE project=?", (project,)
            ).fetchone()
            current = int(row["revision"]) if row else 0
            if current != expected_revision:
                raise DataValidationError(
                    "direct_memory_stale_revision",
                    "The direct-memory project changed since it was read.",
                    details={"expected_revision": expected_revision, "current_revision": current},
                )
            next_revision = current + 1
            yield connection, next_revision
            connection.execute(
                "INSERT INTO projects(project,revision) VALUES(?,?) "
                "ON CONFLICT(project) DO UPDATE SET revision=excluded.revision",
                (project, next_revision),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def backup(self, destination: Path) -> Path:
        target = destination.expanduser().resolve()
        assert_outside_git(target)
        if target == self.path:
            raise DataValidationError(
                "direct_memory_backup_target", "Backup target must be separate."
            )
        if target.exists():
            raise DataValidationError(
                "direct_memory_backup_exists", "Backup refuses to overwrite an existing file."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        source = self.connect()
        try:
            backup_to_path(source, target, self._validate_file)
        finally:
            source.close()
        return target

    def _initialize_or_validate(self) -> None:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            tables = table_names(connection)
            app_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            objects = schema_object_names(connection)
            if not tables and not objects and app_id == 0 and version == 0:
                self._create_schema(connection)
                return
            self._assert_database_identity(connection)
        finally:
            connection.close()

    def _validate_file(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            self._assert_database_identity(connection)
        finally:
            connection.close()

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        create_schema(connection, _DDL, _IMMUTABLE_TABLES, _APPLICATION_ID, _SCHEMA_VERSION)
        self._assert_database_identity(connection)

    @staticmethod
    def _assert_database_identity(connection: sqlite3.Connection) -> None:
        assert_schema_identity(
            connection,
            _TABLES,
            _COLUMNS,
            _IMMUTABLE_TABLES,
            _APPLICATION_ID,
            _SCHEMA_VERSION,
            _DDL,
        )
