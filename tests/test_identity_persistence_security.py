from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from conftest import synthetic_audit

from ynoy.cli.main import main
from ynoy.errors import PolicyViolation
from ynoy.models import BootstrapDeclaration, CandidateKind, DataClass
from ynoy.storage import MemoryMutationRepository


def _declaration(*, synthetic: bool) -> BootstrapDeclaration:
    return BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement="Prefer reversible evidence-backed changes.",
        source_name="synthetic.json" if synthetic else "private.json",
        data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY),
        synthetic=synthetic,
    )


def _real_adopted_payload() -> dict[str, object]:
    return {
        "statement": "Prefer reversible evidence-backed changes.",
        "speaker": "user",
        "claim_holder": "represented_user",
        "source_authority": "explicit_user_statement",
        "adopted": True,
        "evidence_plane": "identity_interpretation",
        "synthetic": False,
    }


def _run_cli(
    arguments: Sequence[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    exit_code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return exit_code, payload


def _database_spy(*, target_exists: bool) -> tuple[MagicMock, MagicMock]:
    database = MagicMock()
    connection = MagicMock()

    def execute(statement: str, *_: object, **__: object) -> MagicMock:
        cursor = MagicMock()
        cursor.rowcount = 1
        normalized = " ".join(statement.split())
        if "pg_try_advisory_xact_lock" in normalized:
            cursor.fetchone.return_value = {"acquired": True}
        elif "AS has_synthetic" in normalized:
            cursor.fetchone.return_value = {
                "has_synthetic": target_exists,
                "has_private": False,
            }
        elif "SELECT subject_id," in normalized and "bootstrap_declarations" in normalized:
            cursor.fetchone.return_value = (
                {"subject_id": "self", "data_class": "D0"} if target_exists else None
            )
        else:
            cursor.fetchone.return_value = None
        return cursor

    connection.execute.side_effect = execute
    database.connect.return_value.__enter__.return_value = connection
    return database, connection


def test_real_bootstrap_cli_blocks_before_database_or_parser(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "real-bootstrap.json"
    source.write_text(json.dumps([_real_adopted_payload()]), encoding="utf-8")
    calls: list[str] = []

    def forbidden(*_: object, **__: object) -> None:
        calls.append("called")
        raise AssertionError("real bootstrap must fail before database or parser work")

    monkeypatch.setattr("ynoy.cli.context.CommandContext.database", forbidden)
    monkeypatch.setattr("ynoy.cli.handlers.bootstrap.load_bootstrap", forbidden)
    exit_code, payload = _run_cli(["bootstrap", "import", str(source)], capsys)

    assert exit_code == 2 and payload["ok"] is False
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == "real_identity_persistence_unsupported"
    assert calls == []


@pytest.mark.parametrize("operation", ["add", "replacement"])
def test_repository_rejects_real_declarations_before_connect(operation: str) -> None:
    database = MagicMock()
    repository = MemoryMutationRepository(database)
    declaration = _declaration(synthetic=False)

    with pytest.raises(PolicyViolation) as blocked:
        if operation == "add":
            repository.add_bootstrap_declarations((declaration,), synthetic_audit())
        else:
            repository.correct(
                target_record_id=uuid4(),
                reason="explicit correction",
                audit_receipt=synthetic_audit(),
                replacement=declaration,
            )

    assert blocked.value.code == "real_identity_persistence_unsupported"
    database.connect.assert_not_called()


@pytest.mark.parametrize("operation", ["add", "replacement"])
def test_repository_synthetic_mutations_reach_database(operation: str) -> None:
    database, connection = _database_spy(target_exists=operation == "replacement")
    repository = MemoryMutationRepository(database)
    declaration = _declaration(synthetic=True)

    if operation == "add":
        assert repository.add_bootstrap_declarations((declaration,), synthetic_audit()) == 1
    else:
        result = repository.correct(
            target_record_id=uuid4(),
            reason="synthetic correction",
            audit_receipt=synthetic_audit(),
            replacement=declaration,
        )
        assert result["status"] == "superseded"
        assert result["replacement_record_id"] == str(declaration.record_id)

    database.connect.assert_called_once_with()
    statements = tuple(str(call.args[0]) for call in connection.execute.call_args_list)
    assert any("pg_try_advisory_xact_lock" in statement for statement in statements)


def test_real_replacement_cli_blocks_before_parser_or_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "real-replacement.json"
    source.write_text(json.dumps([_real_adopted_payload()]), encoding="utf-8")
    calls: list[str] = []

    def fake_database(_: object, *, synthetic: bool) -> object:
        assert synthetic is False
        return object()

    def forbidden(*_: object, **__: object) -> None:
        calls.append("called")
        raise AssertionError("real replacement must fail before parser or mutation")

    monkeypatch.setattr("ynoy.cli.context.CommandContext.database", fake_database)
    monkeypatch.setattr("ynoy.cli.handlers.memory.load_bootstrap", forbidden)
    monkeypatch.setattr("ynoy.cli.handlers.memory.MemoryMutationRepository.correct", forbidden)
    exit_code, payload = _run_cli(
        [
            "memory",
            "correct",
            str(uuid4()),
            "--reason",
            "explicit correction",
            "--replacement",
            str(source),
        ],
        capsys,
    )

    assert exit_code == 2 and payload["ok"] is False
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == "real_identity_persistence_unsupported"
    assert calls == []


def test_real_correction_without_replacement_reaches_mutation(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_id = uuid4()
    observed: dict[str, object] = {}

    def fake_database(_: object, *, synthetic: bool) -> object:
        assert synthetic is False
        return object()

    def fake_correct(*_: object, **kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return {
            "correction_id": str(uuid4()),
            "target_record_id": str(target_id),
            "replacement_record_id": None,
            "status": "invalidated",
        }

    monkeypatch.setattr("ynoy.cli.context.CommandContext.database", fake_database)
    monkeypatch.setattr("ynoy.cli.handlers.memory.MemoryMutationRepository.correct", fake_correct)
    exit_code, payload = _run_cli(
        ["memory", "correct", str(target_id), "--reason", "explicit invalidation"],
        capsys,
    )

    assert exit_code == 0 and payload["ok"] is True
    assert observed["target_record_id"] == target_id
    assert observed["replacement"] is None
    assert observed["subject_id"] == "self"
