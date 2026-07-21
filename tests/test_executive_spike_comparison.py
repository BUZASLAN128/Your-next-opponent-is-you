from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.executive_spike import (
    compare_synthetic_planners,
    start_model_synthetic_mission,
)
from ynoy.executive_spike.contracts import ExecutiveManifest
from ynoy.executive_spike.proposer import LocalExecutiveProposer
from ynoy.util import canonical_sha256


def _proposer() -> LocalExecutiveProposer:
    return LocalExecutiveProposer(
        endpoint="http://127.0.0.1:1234/v1/chat/completions",
        model="fixture-model",
        revision="fixture-revision",
        artifact_sha256="a" * 64,
        local_attested=True,
    )


def _response(decision: str = "apply_config_repair") -> dict[str, object]:
    return {
        "model": "fixture-model",
        "response_text": "MODEL_RESPONSE_MUST_NOT_ENTER_THE_PROJECTION",
        "choices": [{"message": {"content": f'{{"decision":"{decision}"}}'}}],
    }


def test_legacy_deterministic_manifest_remains_readable() -> None:
    payload = {
        "protocol_version": "executive-spike/0.1",
        "mission_id": str(UUID(int=42)),
        "mission": "legacy mission",
        "scenario": "config-repair-v1",
        "created_at": datetime(2026, 7, 21, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
    }
    serialized = {**payload, "manifest_sha256": canonical_sha256(payload)}

    manifest = ExecutiveManifest.model_validate(serialized)

    assert manifest.planner_kind == "deterministic_fixture"
    assert manifest.model_identity is None


def test_comparison_binds_equal_fixture_oracle_and_budget_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ynoy.executive_spike.proposer.post_json",
        lambda *_args, **_kwargs: _response(),
    )

    comparison = compare_synthetic_planners(tmp_path / "private-root", "repair config", _proposer())

    assert comparison.scenario == "config-repair-v1"
    assert comparison.same_fixture is True
    assert comparison.same_oracle is True
    assert comparison.step_budget_per_arm == 8
    assert comparison.model_call_budget == 1
    assert comparison.deterministic.model_used is False
    assert comparison.deterministic.planner_kind == "deterministic_fixture"
    assert comparison.model.model_used is True
    assert comparison.model.planner_kind == "attested_local_model"
    assert comparison.deterministic.status == comparison.model.status == "completed"
    assert tuple(event.kind for event in comparison.deterministic.events) == tuple(
        event.kind for event in comparison.model.events
    )
    assert tuple(event.workspace_sha256 for event in comparison.deterministic.events) == tuple(
        event.workspace_sha256 for event in comparison.model.events
    )


def test_valid_model_proposal_completes_only_the_allowlisted_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def fake_post_json(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append({"args": args, "kwargs": kwargs})
        return _response()

    monkeypatch.setattr("ynoy.executive_spike.proposer.post_json", fake_post_json)
    trace = start_model_synthetic_mission(
        tmp_path / "private-root", "repair config", _proposer(), max_new_steps=8
    )

    assert trace.status == "completed"
    assert tuple(event.kind for event in trace.events) == (
        "mission_started",
        "failure_observed",
        "plan_proposed",
        "patch_applied",
        "test_passed",
        "mission_finished",
    )
    assert len(calls) == 1
    assert trace.model_used is True
    assert trace.model_identity == "fixture-model@fixture-revision:" + "a" * 64


@pytest.mark.parametrize(
    ("response", "case_id"),
    [
        pytest.param(
            {
                "model": "fixture-model",
                "choices": [{"message": {"content": "not-json"}}],
            },
            "malformed",
        ),
        pytest.param(
            {
                "model": "wrong-model",
                "choices": [{"message": {"content": '{"decision":"apply_config_repair"}'}}],
            },
            "wrong-model",
        ),
    ],
)
def test_malformed_or_wrong_model_response_rejects_before_patch_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    response: dict[str, object],
    case_id: str,
) -> None:
    monkeypatch.setattr("ynoy.executive_spike.proposer.post_json", lambda *_a, **_k: response)
    trace = start_model_synthetic_mission(
        tmp_path / f"private-root-{case_id}", "repair config", _proposer(), max_new_steps=8
    )
    workspace = (
        tmp_path
        / f"private-root-{case_id}"
        / "executive-spikes"
        / str(trace.mission_id)
        / "workspace"
    )

    assert trace.status == "rejected_model"
    assert tuple(event.kind for event in trace.events) == (
        "mission_started",
        "failure_observed",
        "model_rejected",
    )
    assert (workspace / "config.json").read_bytes() == b'{"status":"broken","version":1}\n'
    assert not any(event.kind == "patch_applied" for event in trace.events)


def test_model_abstention_has_no_patch_and_no_completion_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ynoy.executive_spike.proposer.post_json",
        lambda *_args, **_kwargs: _response("abstain"),
    )
    trace = start_model_synthetic_mission(
        tmp_path / "private-root", "repair config", _proposer(), max_new_steps=8
    )
    workspace = tmp_path / "private-root" / "executive-spikes" / str(trace.mission_id) / "workspace"

    assert trace.status == "abstained"
    assert tuple(event.kind for event in trace.events) == (
        "mission_started",
        "failure_observed",
        "model_abstained",
    )
    assert (workspace / "config.json").read_bytes() == b'{"status":"broken","version":1}\n'


def test_projection_excludes_response_text_and_promoted_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ynoy.executive_spike.proposer.post_json",
        lambda *_args, **_kwargs: _response(),
    )

    comparison = compare_synthetic_planners(tmp_path / "private-root", "repair config", _proposer())
    serialized = comparison.model_dump_json()

    assert "MODEL_RESPONSE_MUST_NOT_ENTER_THE_PROJECTION" not in serialized
    assert comparison.response_content_emitted is False
    assert comparison.external_action_authority == "none"
    assert comparison.persona_evidence is False
    assert comparison.automatic_core_promotion is False
    assert comparison.deterministic.external_action_authority == "none"
    assert comparison.model.external_action_authority == "none"
    assert comparison.deterministic.persona_evidence is False
    assert comparison.model.persona_evidence is False
    assert comparison.deterministic.automatic_core_promotion is False
    assert comparison.model.automatic_core_promotion is False
    assert comparison.deterministic.send_enabled is False
    assert comparison.model.send_enabled is False
