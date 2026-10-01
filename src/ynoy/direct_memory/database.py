from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from ynoy.direct_memory.backup_publish import backup_to_path
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.direct_memory.database_schema import (
    _COLUMNS,
    _DDL,
    _IMMUTABLE_TABLES,
    _SCHEMA_VERSION,
    _TABLES,
)
from ynoy.direct_memory.plane_guard import (
    assert_no_orphaned_sqlite_sidecars,
    assert_sqlite_header,
    assert_sqlite_initial_state,
    validate_sqlite_storage,
)
from ynoy.direct_memory.schema_checks import (
    assert_schema_identity,
    create_schema,
    schema_object_names,
    table_names,
)
from ynoy.errors import DataValidationError
from ynoy.private_files import create_private_file, create_private_parents, ensure_private_root


class DirectMemoryDatabase:
    def __init__(self, path: Path, *, data_plane: DataPlane = DataPlane.PRIVATE) -> None:
        self.path = path.expanduser().absolute()
        self.private_root = ensure_private_root(self.path.parent)
        self.data_plane = data_plane
        create_private_parents(self.path.parent, private_root=self.private_root)
        newly_created = not os.path.lexists(self.path)
        if newly_created:
            assert_no_orphaned_sqlite_sidecars(self.path, self.private_root)
            create_private_file(self.path, private_root=self.private_root)
        self._initialize_or_validate(newly_created=newly_created)

    def connect(self) -> sqlite3.Connection:
        self._validate_file(self.path, self.private_root)
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

    def revision_snapshot(
        self, project: str | None = None, *, known_at: datetime | None = None
    ) -> dict[str, int]:
        """Capture immutable project revision watermarks from one SQLite snapshot."""
        if known_at is not None and known_at.utcoffset() is None:
            raise DataValidationError(
                "direct_memory_cutoff_invalid", "Temporal cutoffs must be timezone-aware."
            )
        with closing(self.connect()) as connection:
            connection.execute("BEGIN")
            if project is None:
                rows = connection.execute(
                    "SELECT project,revision FROM projects ORDER BY project"
                ).fetchall()
                watermarks = {str(row["project"]): int(row["revision"]) for row in rows}
            else:
                row = connection.execute(
                    "SELECT revision FROM projects WHERE project=?", (project,)
                ).fetchone()
                watermarks = {project: int(row["revision"]) if row else 0}
            if known_at is None:
                return watermarks
            selected = (project,) if project is not None else tuple(watermarks)
            cutoff_text = known_at.astimezone(UTC).isoformat()
            for name in selected:
                if name is None:
                    continue
                row = connection.execute(
                    _FIRST_RECORDED_AFTER_CUTOFF_SQL,
                    (name, name, name, name, name, name, name, cutoff_text),
                ).fetchone()
                first_future_revision = row[0]
                if first_future_revision is not None:
                    watermarks[name] = min(
                        watermarks.get(name, 0), int(first_future_revision) - 1
                    )
        return watermarks

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
            validate_sqlite_storage(self.path, self.private_root)
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
        target = destination.expanduser().absolute()
        if target == self.path:
            raise DataValidationError(
                "direct_memory_backup_target", "Backup target must be separate."
            )
        target_root = ensure_private_root(target.parent)
        create_private_parents(target.parent, private_root=target_root)
        if os.path.lexists(target):
            validate_sqlite_storage(target, target_root)
            raise DataValidationError(
                "direct_memory_backup_exists", "Backup refuses to overwrite an existing file."
            )
        if validate_sqlite_storage(target, target_root, require_database=False):
            raise DataValidationError(
                "direct_memory_backup_exists", "Backup refuses existing SQLite sidecars."
            )
        source = self.connect()
        try:
            backup_to_path(source, target, lambda path: self._validate_file(path, target_root))
        finally:
            source.close()
        return target

    def _initialize_or_validate(self, *, newly_created: bool) -> None:
        assert_sqlite_initial_state(
            self.path,
            self.private_root,
            self.data_plane,
            _SCHEMA_VERSION,
            newly_created=newly_created,
        )
        if not newly_created:
            self._validate_file(self.path, self.private_root)
            return
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

    def _validate_file(self, path: Path, private_root: Path) -> None:
        validate_sqlite_storage(path, private_root)
        assert_sqlite_header(path, self.data_plane, _SCHEMA_VERSION)
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            self._assert_database_identity(connection)
        finally:
            connection.close()

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        create_schema(
            connection,
            _DDL,
            _IMMUTABLE_TABLES,
            self.data_plane.application_id,
            _SCHEMA_VERSION,
        )
        self._assert_database_identity(connection)

    def _assert_database_identity(self, connection: sqlite3.Connection) -> None:
        assert_schema_identity(
            connection,
            _TABLES,
            _COLUMNS,
            _IMMUTABLE_TABLES,
            self.data_plane.application_id,
            _SCHEMA_VERSION,
            _DDL,
        )


_FIRST_RECORDED_AFTER_CUTOFF_SQL = """
SELECT MIN(revision) FROM (
    SELECT revision,recorded_at FROM source_events WHERE project=?
    UNION ALL SELECT revision,recorded_at FROM authorization_uses WHERE project=?
    UNION ALL SELECT revision,recorded_at FROM source_attributions WHERE project=?
    UNION ALL SELECT revision,recorded_at FROM tool_receipts WHERE project=?
    UNION ALL SELECT revision,recorded_at FROM reviews WHERE project=?
    UNION ALL SELECT revision,recorded_at FROM corrections WHERE project=?
    UNION ALL SELECT revision,recorded_at FROM claim_revisions WHERE project=?
) WHERE recorded_at>?
"""
