from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from ynoy.cli.context import CommandContext
from ynoy.config import Settings
from ynoy.database_policy import LIBPQ_ENVIRONMENT_OVERRIDES
from ynoy.errors import PolicyViolation
from ynoy.storage import Database
from ynoy.storage.database import _load_migrations


class SchemaRowsConnection:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows

    def execute(self, _: str) -> SchemaRowsConnection:
        return self

    def fetchall(self) -> list[dict[str, str]]:
        return self.rows


def migration_scenario(
    scenario: str,
) -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    expected = {name: digest for name, _, digest in _load_migrations()}
    rows = [{"migration_id": name, "migration_sha256": digest} for name, digest in expected.items()]
    differences = {"missing": [], "unexpected": [], "mismatched": []}
    if scenario == "missing":
        differences["missing"] = [rows.pop(0)["migration_id"]]
    elif scenario == "missing_002":
        migration = "002_security_lineage_hardening.sql"
        rows = [row for row in rows if row["migration_id"] != migration]
        differences["missing"] = [migration]
    elif scenario == "mismatch":
        rows[0]["migration_sha256"] = "0" * 64
        differences["mismatched"] = [rows[0]["migration_id"]]
    elif scenario == "unexpected":
        rows.append({"migration_id": "999_unexpected.sql", "migration_sha256": "0" * 64})
        differences["unexpected"] = ["999_unexpected.sql"]
    return rows, differences


@pytest.mark.parametrize("scenario", ["missing", "missing_002", "mismatch", "unexpected"])
def test_schema_status_rejects_any_difference_from_packaged_migrations(
    scenario: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in LIBPQ_ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)
    rows, differences = migration_scenario(scenario)
    database = Database("postgresql://user:secret@127.0.0.1:55432/ynoy")

    @contextmanager
    def fake_connect() -> Any:
        yield SchemaRowsConnection(rows)

    monkeypatch.setattr(database, "connect", fake_connect)
    status = database.schema_status()
    with pytest.raises(PolicyViolation) as blocked:
        database.require_current_schema()

    assert status["migration_current"] is False
    assert status["missing_migrations"] == differences["missing"]
    assert status["unexpected_migrations"] == differences["unexpected"]
    assert status["mismatched_migrations"] == differences["mismatched"]
    assert blocked.value.code == "database_schema_not_current"
    assert blocked.value.details == {
        "missing_migrations": differences["missing"],
        "unexpected_migrations": differences["unexpected"],
        "mismatched_migrations": differences["mismatched"],
    }


@pytest.mark.parametrize("synthetic", [True, False])
def test_command_context_stops_before_operations_when_schema_is_not_current(
    synthetic: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class SchemaBlockedDatabase:
        def __init__(self, _: str) -> None:
            events.append("constructed")

        def require_current_schema(self) -> None:
            events.append("schema_checked")
            raise PolicyViolation("database_schema_not_current", "fixture")

        def require_restricted_runtime(self) -> None:
            events.append("runtime_checked")

    for variable in LIBPQ_ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr("ynoy.cli.context.require_private_root", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("ynoy.cli.context.Database", SchemaBlockedDatabase)
    settings = Settings(
        private_root=tmp_path / "private-root",
        postgres_data_path=None,
        database_url="postgresql://user:secret@127.0.0.1:55432/ynoy",
        local_reasoner_url=None,
        local_model_attested=False,
        local_reasoner_model="fixture-model",
        embedding_model="fixture-embedding",
    )

    with pytest.raises(PolicyViolation) as blocked:
        CommandContext(settings=settings, repository_root=tmp_path).database(synthetic=synthetic)

    assert blocked.value.code == "database_schema_not_current"
    assert events == ["constructed", "schema_checked"]
