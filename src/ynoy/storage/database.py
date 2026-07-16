from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from ynoy.constants import PGVECTOR_VERSION, POSTGRES_VERSION
from ynoy.database_policy import require_no_libpq_environment, validated_loopback_hostaddr
from ynoy.errors import PolicyViolation, StorageError
from ynoy.util import canonical_sha256, utc_now

Row = dict[str, Any]


def require_row(row: Row | None, operation: str) -> Row:
    if row is None:
        raise StorageError(
            "database_result_missing",
            f"PostgreSQL returned no result for {operation}.",
        )
    return row


class Database:
    def __init__(self, database_url: str):
        self._database_url = database_url
        self._hostaddr = validated_loopback_hostaddr(database_url)
        require_no_libpq_environment()

    @contextmanager
    def connect(self) -> Iterator[Connection[Row]]:
        require_no_libpq_environment()
        try:
            with psycopg.connect(
                self._database_url,
                hostaddr=self._hostaddr,
                row_factory=dict_row,
            ) as connection:
                yield connection
        except psycopg.Error as exc:
            raise StorageError(
                "database_operation_failed",
                "The private PostgreSQL operation failed; credentials were not included.",
                details={"database_error": exc.__class__.__name__},
            ) from exc

    def migrate(self) -> dict[str, object]:
        applied: list[str] = []
        with self.connect() as connection:
            _verify_server_version(connection)
            _ensure_migration_table(connection)
            for migration_name, sql, digest in _load_migrations():
                if _migration_is_current(connection, migration_name, digest):
                    continue
                connection.execute(sql)
                connection.execute(
                    """
                    INSERT INTO ynoy.schema_migrations
                        (migration_id, migration_sha256, applied_at)
                    VALUES (%s, %s, %s)
                    """,
                    (migration_name, digest, utc_now()),
                )
                applied.append(migration_name)
            _verify_pgvector(connection)
        return {
            "postgres_version": POSTGRES_VERSION,
            "pgvector_version": PGVECTOR_VERSION,
            "applied_migrations": applied,
        }

    def status(self) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT current_setting('server_version') AS postgres_version,
                       current_setting('server_version_num') AS postgres_version_num,
                       current_user AS database_user,
                       (SELECT rolsuper FROM pg_roles
                        WHERE rolname = current_user) AS database_user_is_superuser,
                       has_table_privilege(current_user, 'ynoy.audit_receipts', 'UPDATE')
                           AS audit_can_update,
                       has_table_privilege(current_user, 'ynoy.audit_receipts', 'DELETE')
                           AS audit_can_delete,
                       has_table_privilege(current_user, 'ynoy.audit_receipts', 'TRUNCATE')
                           AS audit_can_truncate,
                       has_table_privilege(current_user, 'ynoy.audit_receipts', 'INSERT')
                           AS audit_can_insert,
                       (SELECT extversion FROM pg_extension
                        WHERE extname = 'vector') AS pgvector_version,
                       (SELECT count(*) FROM ynoy.schema_migrations) AS migration_count
                """
            ).fetchone()
            status = dict(require_row(row, "database status"))
            status.update(_schema_status(connection))
            if int(status["postgres_version_num"]) == 180004:
                status["postgres_version"] = POSTGRES_VERSION
            return status

    def schema_status(self) -> dict[str, object]:
        with self.connect() as connection:
            return _schema_status(connection)

    def require_current_schema(self) -> None:
        status = self.schema_status()
        if not bool(status["migration_current"]):
            raise PolicyViolation(
                "database_schema_not_current",
                "Apply the exact packaged migrations before using the database.",
                details={
                    "missing_migrations": status["missing_migrations"],
                    "unexpected_migrations": status["unexpected_migrations"],
                    "mismatched_migrations": status["mismatched_migrations"],
                },
            )

    def require_restricted_runtime(self) -> None:
        status = self.status()
        unsafe_audit_privilege = any(
            bool(status.get(name))
            for name in ("audit_can_update", "audit_can_delete", "audit_can_truncate")
        )
        if bool(status.get("database_user_is_superuser")) or unsafe_audit_privilege:
            raise PolicyViolation(
                "database_superuser_blocked_for_real_data",
                "Real data requires a restricted runtime role without audit mutation rights.",
            )
        if not bool(status.get("audit_can_insert")):
            raise PolicyViolation(
                "database_audit_insert_required",
                "The restricted runtime role must be able to append audit receipts.",
            )


def _verify_server_version(connection: Connection[Row]) -> None:
    row = require_row(
        connection.execute("SELECT current_setting('server_version_num') AS value").fetchone(),
        "server version check",
    )
    version_num = int(row["value"])
    if version_num != 180004:
        raise StorageError(
            "postgres_version_mismatch",
            f"Expected PostgreSQL {POSTGRES_VERSION}; found version number {version_num}.",
        )


def _ensure_migration_table(connection: Connection[Row]) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS ynoy")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ynoy.schema_migrations (
            migration_id text PRIMARY KEY,
            migration_sha256 text NOT NULL,
            applied_at timestamptz NOT NULL
        )
        """
    )


def _load_migrations() -> list[tuple[str, str, str]]:
    root = resources.files("ynoy").joinpath("migrations")
    files = sorted(
        (item for item in root.iterdir() if item.name.endswith(".sql")),
        key=lambda item: item.name,
    )
    migrations: list[tuple[str, str, str]] = []
    for item in files:
        sql = item.read_text(encoding="utf-8")
        migrations.append((item.name, sql, canonical_sha256({"sql": sql})))
    return migrations


def _migration_is_current(connection: Connection[Row], migration_name: str, digest: str) -> bool:
    existing = connection.execute(
        "SELECT migration_sha256 FROM ynoy.schema_migrations WHERE migration_id = %s",
        (migration_name,),
    ).fetchone()
    if existing is None:
        return False
    if existing["migration_sha256"] != digest:
        raise StorageError(
            "migration_digest_mismatch",
            f"Applied migration {migration_name} differs from source.",
        )
    return True


def _verify_pgvector(connection: Connection[Row]) -> None:
    row = connection.execute(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()
    found = row["extversion"] if row else "missing"
    if found != PGVECTOR_VERSION:
        raise StorageError(
            "pgvector_version_mismatch",
            f"Expected pgvector {PGVECTOR_VERSION}; found {found}.",
        )


def _schema_status(connection: Connection[Row]) -> dict[str, object]:
    expected = {name: digest for name, _, digest in _load_migrations()}
    rows = connection.execute(
        "SELECT migration_id, migration_sha256 FROM ynoy.schema_migrations"
    ).fetchall()
    applied = {str(row["migration_id"]): str(row["migration_sha256"]) for row in rows}
    missing = sorted(expected.keys() - applied.keys())
    unexpected = sorted(applied.keys() - expected.keys())
    mismatched = sorted(
        name for name in expected.keys() & applied.keys() if expected[name] != applied[name]
    )
    return {
        "migration_current": not missing and not unexpected and not mismatched,
        "expected_migration_count": len(expected),
        "applied_migration_count": len(applied),
        "missing_migrations": missing,
        "unexpected_migrations": unexpected,
        "mismatched_migrations": mismatched,
    }
