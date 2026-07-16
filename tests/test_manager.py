from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from ynoy.cli.main import main
from ynoy.manager import start_manager
from ynoy.models import (
    BootstrapDeclaration,
    ClaimCandidate,
    ClaimHolder,
    DataClass,
    EvidenceRegime,
    ManagerStartResult,
    ScopeRef,
    SourceAuthority,
)

EXPECTED_RULES = (
    (
        "evidence_honesty",
        "Separate observed facts, explicit user statements, and hypotheses.",
    ),
    (
        "bounded_learning",
        "Ask one bounded question when personal evidence is missing.",
    ),
    (
        "reversible_progress",
        "Propose the smallest reversible step and require focused verification.",
    ),
    (
        "no_false_action",
        "Never claim that an external action or memory promotion occurred.",
    ),
)


def _run_cli(
    arguments: Sequence[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    exit_code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return exit_code, payload


def _remove_manager_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "YNOY_DATABASE_URL",
        "YNOY_PRIVATE_ROOT",
        "YNOY_LOCAL_REASONER_URL",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_start_manager_returns_deterministic_zero_persona_contract() -> None:
    result = start_manager(
        task="Help me review a risky code change.",
        scope=ScopeRef(project="pilot", risk="high"),
    )
    repeated = start_manager(
        task="Plan a reversible implementation step.",
        scope=ScopeRef(project="another-project", risk="low"),
    )

    assert isinstance(result, ManagerStartResult)
    assert result.status == "ready"
    assert result.database_used is False and result.provider_used is False
    assert result.task_data_class == DataClass.PRIVATE_TASK
    assert result.persistence_status == "not_persisted"
    assert result.audit_status == "not_persisted_no_database"
    memory = result.operating_memory
    assert memory == repeated.operating_memory
    assert memory.memory_kind == "system_operating_seed"
    assert memory.evidence_regime == EvidenceRegime.ZERO
    assert memory.persona_memory_state == "empty" and memory.persona_evidence_count == 0
    assert memory.source_authority == SourceAuthority.SYSTEM_CONTROL
    assert memory.data_class == DataClass.PUBLIC_SYNTHETIC
    assert memory.persistence == "ephemeral"
    assert memory.automatic_core_promotion is False
    assert tuple((rule.rule_id, rule.instruction) for rule in memory.rules) == EXPECTED_RULES


def test_operating_rules_never_become_persona_or_represented_user_evidence() -> None:
    memory = start_manager(task="Review this plan.", scope=ScopeRef()).operating_memory

    assert not isinstance(memory, BootstrapDeclaration | ClaimCandidate)
    for rule in memory.rules:
        assert not isinstance(rule, BootstrapDeclaration | ClaimCandidate)
        assert rule.persona_evidence is False
        assert rule.source_authority == SourceAuthority.SYSTEM_CONTROL
        assert rule.data_class == DataClass.PUBLIC_SYNTHETIC
        assert getattr(rule, "claim_holder", None) != ClaimHolder.REPRESENTED_USER
        assert "represented_user" not in json.dumps(rule.model_dump(mode="json"))


def test_manager_advisory_is_generic_unknown_and_has_no_action_authority() -> None:
    advisory = start_manager(task="Choose an implementation.", scope=ScopeRef()).advisory

    assert advisory.answer.startswith("Generic advice:")
    assert advisory.answer_kind == "system_advisory"
    assert advisory.personal_fit == "unknown"
    assert advisory.authority == "none"
    assert advisory.proposed_action is None
    assert advisory.action_status == "not_performed"
    assert advisory.action_receipt is None
    assert advisory.evidence_receipts == ()
    assert advisory.question is not None and advisory.question.strip()
    assert advisory.question.count("?") == 1


def test_manager_cli_works_without_database_private_root_or_provider(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_calls: list[str] = []

    def forbidden_dependency(*_: object, **__: object) -> None:
        dependency_calls.append("called")
        raise AssertionError("manager cold start must not call a database or provider")

    _remove_manager_dependencies(monkeypatch)
    monkeypatch.setattr("ynoy.storage.database.psycopg.connect", forbidden_dependency)
    monkeypatch.setattr("ynoy.local_http.build_opener", forbidden_dependency)
    exit_code, payload = _run_cli(
        ["manager", "start", "--task", "Review this implementation."], capsys
    )

    assert exit_code == 0 and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    assert result["status"] == "ready"
    assert result["database_used"] is False and result["provider_used"] is False
    assert result["task_data_class"] == "D1"
    assert result["persistence_status"] == "not_persisted"
    assert result["audit_status"] == "not_persisted_no_database"
    assert result["operating_memory"]["persona_memory_state"] == "empty"
    assert result["advisory"]["action_status"] == "not_performed"
    assert result["advisory"]["question"] is not None
    assert dependency_calls == []


@pytest.mark.parametrize(
    ("task", "error_code"),
    [
        pytest.param("   ", "task_required", id="empty"),
        pytest.param("ş" * 32_769, "task_size_limit", id="oversized"),
    ],
)
def test_manager_cli_rejects_empty_and_oversized_tasks(
    task: str,
    error_code: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _remove_manager_dependencies(monkeypatch)
    exit_code, payload = _run_cli(
        ["manager", "start", "--task", task],
        capsys,
    )

    assert exit_code == 2 and payload["ok"] is False
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == error_code
