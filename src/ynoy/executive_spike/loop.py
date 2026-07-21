from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ynoy.errors import AdapterError, DataValidationError
from ynoy.executive_spike.contracts import (
    ExecutiveComparison,
    ExecutiveEvent,
    ExecutiveManifest,
    ExecutiveTrace,
    MissionStatus,
    PlannerKind,
)
from ynoy.executive_spike.fixture import (
    apply_known_patch,
    initialize_workspace,
    observe_failure,
    verify_success,
    workspace_digest,
)
from ynoy.executive_spike.proposer import (
    DeterministicFixturePlanner,
    ExecutivePlanner,
    LocalExecutiveProposer,
)
from ynoy.executive_spike.store import ExecutiveSpikeStore

_MAX_NEW_STEPS = 8


def start_synthetic_mission(private_root: Path, mission: str, max_new_steps: int) -> ExecutiveTrace:
    """Create a D0-only fixture mission and advance its bounded executive loop."""
    return _start_mission(private_root, mission, max_new_steps, DeterministicFixturePlanner())


def start_model_synthetic_mission(
    private_root: Path, mission: str, proposer: LocalExecutiveProposer, max_new_steps: int
) -> ExecutiveTrace:
    """Run one bounded model-proposal mission while deterministic code retains all actions."""
    return _start_mission(private_root, mission, max_new_steps, proposer)


def compare_synthetic_planners(
    private_root: Path, mission: str, proposer: LocalExecutiveProposer
) -> ExecutiveComparison:
    """Compare equal-budget deterministic and local-model planners on separate D0 fixtures."""
    deterministic = start_synthetic_mission(private_root, mission, _MAX_NEW_STEPS)
    model = start_model_synthetic_mission(private_root, mission, proposer, _MAX_NEW_STEPS)
    return ExecutiveComparison(deterministic=deterministic, model=model)


def _start_mission(
    private_root: Path, mission: str, max_new_steps: int, planner: ExecutivePlanner
) -> ExecutiveTrace:
    store = ExecutiveSpikeStore(private_root)
    manifest = store.create(
        mission,
        planner_kind=_planner_kind(planner),
        model_identity=planner.model_identity,
    )
    workspace = initialize_workspace(store.mission_root(manifest.mission_id))
    store.append(
        manifest.mission_id,
        "mission_started",
        "Created config-repair-v1 synthetic mission.",
        workspace_digest(workspace),
    )
    return _advance(store, manifest, max_new_steps, planner)


def resume_synthetic_mission(
    private_root: Path, mission_id: UUID, max_new_steps: int
) -> ExecutiveTrace:
    """Reconstruct a mission from its immutable log and continue its next safe step."""
    store = ExecutiveSpikeStore(private_root)
    manifest = store.manifest(mission_id)
    if manifest.planner_kind != "deterministic_fixture":
        raise DataValidationError(
            "executive_model_resume_requires_proposer",
            "Model-planned missions require the attested proposer on resume.",
        )
    return _advance(store, manifest, max_new_steps, DeterministicFixturePlanner())


def trace_mission(private_root: Path, mission_id: UUID) -> ExecutiveTrace:
    """Read and validate the D0 trace without model, database, or action access."""
    store = ExecutiveSpikeStore(private_root)
    return _trace(store.manifest(mission_id), store.events(mission_id))


def _advance(
    store: ExecutiveSpikeStore,
    manifest: ExecutiveManifest,
    max_new_steps: int,
    planner: ExecutivePlanner,
) -> ExecutiveTrace:
    if not 1 <= max_new_steps <= _MAX_NEW_STEPS:
        raise DataValidationError(
            "executive_step_budget_invalid", "Step budget must be between 1 and 8."
        )
    for _ in range(max_new_steps):
        events = store.events(manifest.mission_id)
        if _is_finished(events):
            return _trace(manifest, events)
        _perform_next(store, manifest, events, planner)
    events = store.events(manifest.mission_id)
    if not _is_finished(events):
        workspace = store.mission_root(manifest.mission_id) / "workspace"
        store.append(
            manifest.mission_id,
            "step_budget_paused",
            "Invocation step budget reached; mission may resume.",
            workspace_digest(workspace),
        )
    return _trace(manifest, store.events(manifest.mission_id))


def _perform_next(
    store: ExecutiveSpikeStore,
    manifest: ExecutiveManifest,
    events: tuple[ExecutiveEvent, ...],
    planner: ExecutivePlanner,
) -> None:
    workspace = store.mission_root(manifest.mission_id) / "workspace"
    kinds = {event.kind for event in events}
    if "failure_observed" not in kinds:
        summary, digest = observe_failure(workspace)
        store.append(manifest.mission_id, "failure_observed", summary, digest)
    elif "plan_proposed" not in kinds:
        _record_plan(store, manifest, planner, workspace)
    elif "patch_applied" not in kinds:
        summary, digest = apply_known_patch(workspace)
        store.append(manifest.mission_id, "patch_applied", summary, digest)
    elif "test_passed" not in kinds:
        summary, digest = verify_success(workspace)
        store.append(manifest.mission_id, "test_passed", summary, digest)
    else:
        store.append(
            manifest.mission_id,
            "mission_finished",
            "Mission finished with a verified synthetic outcome.",
            workspace_digest(workspace),
        )


def _record_plan(
    store: ExecutiveSpikeStore,
    manifest: ExecutiveManifest,
    planner: ExecutivePlanner,
    workspace: Path,
) -> None:
    try:
        proposal = planner.propose()
    except AdapterError:
        store.append(
            manifest.mission_id,
            "model_rejected",
            "Local model proposal was rejected by the strict D0 contract.",
            workspace_digest(workspace),
        )
        return
    if not proposal.is_apply():
        store.append(
            manifest.mission_id,
            "model_abstained",
            "Planner abstained; no synthetic patch was applied.",
            workspace_digest(workspace),
        )
        return
    store.append(
        manifest.mission_id,
        "plan_proposed",
        "Proposal selected the bounded config-repair-v1 patch, then verification.",
        workspace_digest(workspace),
    )


def _trace(manifest: ExecutiveManifest, events: tuple[ExecutiveEvent, ...]) -> ExecutiveTrace:
    if not events:
        raise DataValidationError("executive_trace_empty", "Mission has no events.")
    status = _status(events)
    return ExecutiveTrace(
        mission_id=manifest.mission_id,
        status=status,
        event_count=len(events),
        events=events,
        model_used=manifest.planner_kind == "attested_local_model",
        planner_kind=manifest.planner_kind,
        model_identity=manifest.model_identity,
    )


def _is_finished(events: tuple[ExecutiveEvent, ...]) -> bool:
    terminal_kinds = {"mission_finished", "model_abstained", "model_rejected"}
    return any(event.kind in terminal_kinds for event in events)


def _status(events: tuple[ExecutiveEvent, ...]) -> MissionStatus:
    kinds = {event.kind for event in events}
    if "mission_finished" in kinds:
        return "completed"
    if "model_abstained" in kinds:
        return "abstained"
    if "model_rejected" in kinds:
        return "rejected_model"
    return "paused_budget"


def _planner_kind(planner: ExecutivePlanner) -> PlannerKind:
    kind = planner.planner_kind
    if kind not in {"deterministic_fixture", "attested_local_model"}:
        raise DataValidationError("executive_planner_invalid", "Executive planner kind is invalid.")
    if kind == "deterministic_fixture":
        return "deterministic_fixture"
    return "attested_local_model"
