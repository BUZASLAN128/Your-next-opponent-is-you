from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from conftest import _validate_test_database_url

from ynoy.cli.context import CommandContext
from ynoy.config import Settings
from ynoy.database_policy import (
    LIBPQ_ENVIRONMENT_OVERRIDES,
    require_local_database,
    require_no_libpq_environment,
)
from ynoy.errors import PolicyViolation
from ynoy.storage import Database


def clear_libpq_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in LIBPQ_ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:password@127.0.0.1:55432/ynoy_test",
        "postgres://user:password@localhost/ynoy_test",
        "postgresql://user:password@[::1]:5432/ynoy_test",
    ],
)
def test_database_guard_accepts_only_named_loopback_database(database_url: str) -> None:
    _validate_test_database_url(database_url)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:password@db.example/ynoy_test",
        "postgresql://user:password@127.0.0.1/ynoy",
        "sqlite:///ynoy_test",
        "postgresql:///ynoy_test",
        "postgresql://user:password@127.0.0.1/ynoy_test/other",
        "postgresql://user:password@127.0.0.1/ynoy_test#remote",
        "postgresql://user:password@127.0.0.1/ynoy_test?host=db.example",
        "postgresql://user:password@127.0.0.1/ynoy_test?dbname=production",
        "postgresql://user:password@[::1/ynoy_test",
    ],
)
def test_database_guard_rejects_remote_wrong_or_overridden_targets(database_url: str) -> None:
    with pytest.raises(ValueError, match="database ynoy_test"):
        _validate_test_database_url(database_url)


@pytest.mark.parametrize(
    "connection_options",
    [
        "?host=db.example",
        "?hostaddr=203.0.113.10",
        "?dbname=production",
        "?service=production",
        "?servicefile=C%3A%5Cprivate%5Cpg_service.conf",
        "?passfile=C%3A%5Cprivate%5Cpgpass",
        "?application_name=ynoy",
        "#benign-looking-fragment",
    ],
)
def test_local_database_policy_rejects_all_query_and_fragment_options(
    connection_options: str,
    tmp_path: Path,
) -> None:
    database_url = "postgresql://user:secret@127.0.0.1:55432/ynoy" + connection_options
    with pytest.raises(PolicyViolation) as blocked:
        require_local_database(
            database_url,
            private_root=tmp_path,
            postgres_data_path=None,
            real_data=False,
        )
    assert blocked.value.code == "database_connection_options_blocked"


@pytest.mark.parametrize("variable", sorted(LIBPQ_ENVIRONMENT_OVERRIDES))
def test_every_libpq_environment_override_is_rejected(variable: str) -> None:
    with pytest.raises(PolicyViolation) as blocked:
        require_no_libpq_environment({variable: "synthetic-override"})
    assert blocked.value.code == "database_environment_options_blocked"
    assert blocked.value.details == {"variables": [variable]}


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://127.0.0.1:55432/ynoy",
        "postgresql://user@127.0.0.1:55432/ynoy",
        "postgresql://user:secret@127.0.0.1:55432/",
        "postgresql://user:secret@127.0.0.1:55432/ynoy/other",
    ],
)
def test_local_database_requires_explicit_credentials_and_one_database(
    database_url: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(PolicyViolation) as blocked:
        require_local_database(
            database_url,
            private_root=tmp_path,
            postgres_data_path=None,
            real_data=False,
        )
    assert blocked.value.code == "database_url_incomplete"


@pytest.mark.parametrize("context_method", ["database", "setup_database"])
def test_command_context_rejects_connection_options_before_database_construction(
    context_method: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_calls = 0

    def unexpected_database(_: str) -> None:
        nonlocal database_calls
        database_calls += 1
        raise AssertionError("blocked connection options must not construct Database")

    monkeypatch.setattr("ynoy.cli.context.Database", unexpected_database)
    settings = Settings(
        private_root=tmp_path / "private-root",
        postgres_data_path=None,
        database_url="postgresql://user:secret@localhost/ynoy?application_name=ynoy",
        local_reasoner_url=None,
        local_model_attested=False,
        local_reasoner_model="fixture-model",
        embedding_model="fixture-embedding",
    )
    context = CommandContext(settings=settings, repository_root=tmp_path)

    with pytest.raises(PolicyViolation) as blocked:
        if context_method == "database":
            context.database(synthetic=True)
        else:
            context.setup_database()

    assert blocked.value.code == "database_connection_options_blocked"
    assert database_calls == 0


@pytest.mark.parametrize("context_method", ["database", "setup_database"])
def test_command_context_rejects_libpq_environment_before_database_construction(
    context_method: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_calls = 0

    def unexpected_database(_: str) -> None:
        nonlocal database_calls
        database_calls += 1
        raise AssertionError("blocked libpq environment must not construct Database")

    clear_libpq_environment(monkeypatch)
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.10")
    monkeypatch.setattr("ynoy.cli.context.Database", unexpected_database)
    settings = Settings(
        private_root=tmp_path / "private-root",
        postgres_data_path=None,
        database_url="postgresql://user:secret@localhost:55432/ynoy",
        local_reasoner_url=None,
        local_model_attested=False,
        local_reasoner_model="fixture-model",
        embedding_model="fixture-embedding",
    )
    context = CommandContext(settings=settings, repository_root=tmp_path)

    with pytest.raises(PolicyViolation) as blocked:
        if context_method == "database":
            context.database(synthetic=True)
        else:
            context.setup_database()

    assert blocked.value.code == "database_environment_options_blocked"
    assert database_calls == 0


@pytest.mark.parametrize(
    ("database_url", "expected_hostaddr"),
    [
        ("postgresql://user:secret@localhost:55432/ynoy", "127.0.0.1"),
        ("postgresql://user:secret@127.0.0.1:55432/ynoy", "127.0.0.1"),
        ("postgresql://user:secret@[::1]:55432/ynoy", "::1"),
    ],
)
def test_database_connect_pins_psycopg_to_literal_loopback_hostaddr(
    database_url: str,
    expected_hostaddr: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_libpq_environment(monkeypatch)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connect = MagicMock(return_value=connection)
    monkeypatch.setattr("ynoy.storage.database.psycopg.connect", connect)

    with Database(database_url).connect() as yielded:
        assert yielded is connection

    assert connect.call_count == 1
    assert connect.call_args.args == (database_url,)
    assert connect.call_args.kwargs["hostaddr"] == expected_hostaddr
