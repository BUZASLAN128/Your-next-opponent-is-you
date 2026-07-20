from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from ynoy.cli.main import main
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.executive_spike import (
    resume_synthetic_mission,
    start_synthetic_mission,
    trace_mission,
)
from ynoy.executive_spike.contracts import ExecutiveTrace


def _kinds(trace: ExecutiveTrace) -> tuple[str, ...]:
    return tuple(event.kind for event in trace.events)


def _run_cli(arguments: Sequence[str], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    exit_code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict) and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    return result


def test_start_pauses_at_budget_then_resume_completes_exact_trace(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "private-root"

    paused = start_synthetic_mission(private_root, "repair config", max_new_steps=3)

    assert paused.status == "paused_budget"
    assert paused.event_count == 5
    assert _kinds(paused) == (
        "mission_started",
        "failure_observed",
        "plan_proposed",
        "patch_applied",
        "step_budget_paused",
    )

    completed = resume_synthetic_mission(private_root, paused.mission_id, max_new_steps=8)

    assert completed.status == "completed"
    assert completed.event_count == 7
    assert _kinds(completed) == (
        "mission_started",
        "failure_observed",
        "plan_proposed",
        "patch_applied",
        "step_budget_paused",
        "test_passed",
        "mission_finished",
    )
    assert trace_mission(private_root, paused.mission_id) == completed


def test_trace_is_read_only_for_the_private_mission_store(tmp_path: Path) -> None:
    private_root = tmp_path / "private-root"
    started = start_synthetic_mission(private_root, "repair config", max_new_steps=3)
    mission_root = private_root / "executive-spikes" / str(started.mission_id)
    before = {
        path.relative_to(mission_root): path.read_bytes()
        for path in mission_root.rglob("*")
        if path.is_file()
    }

    traced = trace_mission(private_root, started.mission_id)

    after = {
        path.relative_to(mission_root): path.read_bytes()
        for path in mission_root.rglob("*")
        if path.is_file()
    }
    assert traced == started
    assert after == before


def test_tampered_event_fails_closed(tmp_path: Path) -> None:
    private_root = tmp_path / "private-root"
    started = start_synthetic_mission(private_root, "repair config", max_new_steps=3)
    event_path = (
        private_root / "executive-spikes" / str(started.mission_id) / "events" / "00000002.json"
    )
    event_path.write_bytes(
        event_path.read_bytes().replace(b"failure_observed", b"plan_proposed", 1)
    )

    with pytest.raises(DataValidationError) as error:
        trace_mission(private_root, started.mission_id)

    assert error.value.code == "executive_event_invalid"


def test_private_root_inside_git_is_denied(tmp_path: Path) -> None:
    git_root = tmp_path / "repo"
    (git_root / ".git").mkdir(parents=True)

    with pytest.raises(PolicyViolation) as error:
        start_synthetic_mission(git_root, "repair config", max_new_steps=1)

    assert error.value.code == "private_root_inside_git"


def test_manager_spike_cli_round_trips_start_and_resume(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_root = tmp_path / "private-root"
    start = _run_cli(
        [
            "--private-root",
            str(private_root),
            "manager",
            "spike-start",
            "--mission",
            "repair config",
            "--synthetic",
            "--max-new-steps",
            "3",
        ],
        capsys,
    )
    assert start["status"] == "paused_budget"
    mission_id = start["mission_id"]
    assert isinstance(mission_id, str)

    resumed = _run_cli(
        [
            "--private-root",
            str(private_root),
            "manager",
            "spike-resume",
            mission_id,
            "--synthetic",
            "--max-new-steps",
            "8",
        ],
        capsys,
    )
    assert resumed["status"] == "completed"
    assert [event["kind"] for event in resumed["events"]] == [
        "mission_started",
        "failure_observed",
        "plan_proposed",
        "patch_applied",
        "step_budget_paused",
        "test_passed",
        "mission_finished",
    ]
