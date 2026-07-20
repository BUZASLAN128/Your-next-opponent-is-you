from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ynoy.errors import DataValidationError
from ynoy.executive_spike.contracts import ExecutiveEvent, ExecutiveTrace, MissionStatus
from ynoy.executive_spike.fixture import (
    apply_known_patch,
    initialize_workspace,
    observe_failure,
    verify_success,
    workspace_digest,
)
from ynoy.executive_spike.store import ExecutiveSpikeStore

_MAX_NEW_STEPS = 8


def start_synthetic_mission(private_root: Path, mission: str, max_new_steps: int) -> ExecutiveTrace:
    """Create a D0-only fixture mission and advance its bounded executive loop."""
    store = ExecutiveSpikeStore(private_root)
    manifest = store.create(mission)
    workspace = initialize_workspace(store.mission_root(manifest.mission_id))
    store.append(
        manifest.mission_id,
        "mission_started",
        "Created config-repair-v1 synthetic mission.",
        workspace_digest(workspace),
    )
    return _advance(store, manifest.mission_id, max_new_steps)


def resume_synthetic_mission(
    private_root: Path, mission_id: UUID, max_new_steps: int
) -> ExecutiveTrace:
    """Reconstruct a mission from its immutable log and continue its next safe step."""
    store = ExecutiveSpikeStore(private_root)
    store.manifest(mission_id)
    return _advance(store, mission_id, max_new_steps)


def trace_mission(private_root: Path, mission_id: UUID) -> ExecutiveTrace:
    """Read and validate the D0 trace without model, database, or action access."""
    store = ExecutiveSpikeStore(private_root)
    return _trace(mission_id, store.events(mission_id))


def _advance(store: ExecutiveSpikeStore, mission_id: UUID, max_new_steps: int) -> ExecutiveTrace:
    if not 1 <= max_new_steps <= _MAX_NEW_STEPS:
        raise DataValidationError(
            "executive_step_budget_invalid", "Step budget must be between 1 and 8."
        )
    for _ in range(max_new_steps):
        events = store.events(mission_id)
        if _is_finished(events):
            return _trace(mission_id, events)
        _perform_next(store, mission_id, events)
    events = store.events(mission_id)
    if not _is_finished(events):
        workspace = store.mission_root(mission_id) / "workspace"
        store.append(
            mission_id,
            "step_budget_paused",
            "Invocation step budget reached; mission may resume.",
            workspace_digest(workspace),
        )
    return _trace(mission_id, store.events(mission_id))


def _perform_next(
    store: ExecutiveSpikeStore, mission_id: UUID, events: tuple[ExecutiveEvent, ...]
) -> None:
    workspace = store.mission_root(mission_id) / "workspace"
    kinds = {event.kind for event in events}
    if "failure_observed" not in kinds:
        summary, digest = observe_failure(workspace)
        store.append(mission_id, "failure_observed", summary, digest)
    elif "plan_proposed" not in kinds:
        store.append(
            mission_id,
            "plan_proposed",
            "Proposal: apply the bounded config-repair-v1 patch, then verify.",
            workspace_digest(workspace),
        )
    elif "patch_applied" not in kinds:
        summary, digest = apply_known_patch(workspace)
        store.append(mission_id, "patch_applied", summary, digest)
    elif "test_passed" not in kinds:
        summary, digest = verify_success(workspace)
        store.append(mission_id, "test_passed", summary, digest)
    else:
        store.append(
            mission_id,
            "mission_finished",
            "Mission finished with a verified synthetic outcome.",
            workspace_digest(workspace),
        )


def _trace(mission_id: UUID, events: tuple[ExecutiveEvent, ...]) -> ExecutiveTrace:
    if not events:
        raise DataValidationError("executive_trace_empty", "Mission has no events.")
    status: MissionStatus = "completed" if _is_finished(events) else "paused_budget"
    return ExecutiveTrace(
        mission_id=mission_id, status=status, event_count=len(events), events=events
    )


def _is_finished(events: tuple[ExecutiveEvent, ...]) -> bool:
    return any(event.kind == "mission_finished" for event in events)
