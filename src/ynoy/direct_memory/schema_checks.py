from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping, Sequence

from ynoy.errors import DataValidationError


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def schema_object_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    }


def create_schema(
    connection: sqlite3.Connection,
    ddl: Sequence[str],
    immutable_tables: set[str],
    application_id: int,
    schema_version: int,
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in ddl:
            connection.execute(statement)
        for table in sorted(immutable_tables):
            for operation in ("UPDATE", "DELETE"):
                connection.execute(_trigger_statement(table, operation))
        connection.execute(f"PRAGMA application_id={application_id}")
        connection.execute(f"PRAGMA user_version={schema_version}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def assert_schema_identity(
    connection: sqlite3.Connection,
    tables_expected: set[str],
    columns_expected: Mapping[str, Sequence[str]],
    immutable_tables: set[str],
    application_id: int,
    schema_version: int,
    ddl: Sequence[str],
) -> None:
    tables = table_names(connection)
    app_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if tables != tables_expected or app_id != application_id or version != schema_version:
        raise _identity_error("Database identity or schema does not match direct-memory storage.")
    _verify_columns(connection, columns_expected)
    _verify_definitions(connection, ddl, immutable_tables)


def _trigger_statement(table: str, operation: str) -> str:
    return (
        f"CREATE TRIGGER immutable_{table}_{operation.lower()} "
        f"BEFORE {operation} ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'append-only direct-memory record'); END"
    )


def _verify_columns(
    connection: sqlite3.Connection, columns_expected: Mapping[str, Sequence[str]]
) -> None:
    for table, columns in columns_expected.items():
        actual = tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))
        if actual != tuple(columns):
            raise _identity_error("Database column layout failed identity checks.")


def _verify_definitions(
    connection: sqlite3.Connection, ddl: Sequence[str], immutable_tables: set[str]
) -> None:
    expected = {}
    for statement in ddl:
        match = re.match(r"\s*CREATE\s+(TABLE|INDEX)\s+([A-Za-z0-9_]+)", statement, re.I)
        if match is None:
            raise _identity_error("Expected schema DDL is malformed.")
        expected[(match.group(1).casefold(), match.group(2))] = _normalize(statement)
    for table in immutable_tables:
        for operation in ("UPDATE", "DELETE"):
            statement = _trigger_statement(table, operation)
            name = f"immutable_{table}_{operation.lower()}"
            expected[("trigger", name)] = _normalize(statement)
    rows = connection.execute(
        "SELECT type,name,sql FROM sqlite_master "
        "WHERE type IN ('table','index','trigger') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    actual = {(row["type"], row["name"]): _normalize(row["sql"] or "") for row in rows}
    if actual != expected:
        raise _identity_error("Database DDL or append-only trigger definitions do not match.")


def _normalize(statement: str) -> str:
    return " ".join(statement.casefold().split())


def _identity_error(message: str) -> DataValidationError:
    return DataValidationError("direct_memory_database_identity", message)


__all__ = ["assert_schema_identity", "create_schema", "schema_object_names", "table_names"]
