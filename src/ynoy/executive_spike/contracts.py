from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.util import canonical_sha256

EventKind = Literal[
    "mission_started",
    "failure_observed",
    "plan_proposed",
    "patch_applied",
    "test_passed",
    "mission_finished",
    "step_budget_paused",
]
MissionStatus = Literal["completed", "paused_budget"]


class ExecutiveManifest(StrictModel):
    """Immutable D0 mission metadata for one generated fixture."""

    protocol_version: Literal["executive-spike/0.1"] = "executive-spike/0.1"
    mission_id: UUID
    mission: str = Field(min_length=1, max_length=512)
    scenario: Literal["config-repair-v1"] = "config-repair-v1"
    created_at: datetime
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def manifest_is_canonical(self) -> ExecutiveManifest:
        _require_digest(self, "manifest_sha256")
        return self


class ExecutiveEvent(StrictModel):
    """One immutable transition in a mission event chain."""

    mission_id: UUID
    revision: int = Field(ge=1, le=32)
    kind: EventKind
    summary: str = Field(min_length=1, max_length=240)
    workspace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_event_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def event_is_canonical(self) -> ExecutiveEvent:
        _require_digest(self, "event_sha256")
        return self


class ExecutiveTrace(StrictModel):
    """Public D0 projection of a bounded synthetic mission."""

    mission_id: UUID
    status: MissionStatus
    event_count: int = Field(ge=1, le=32)
    events: tuple[ExecutiveEvent, ...]
    model_authority: Literal["proposal_only"] = "proposal_only"
    model_used: Literal[False] = False
    planner_kind: Literal["deterministic_fixture"] = "deterministic_fixture"
    observer_authority: Literal["synthetic_fixture_only"] = "synthetic_fixture_only"
    external_action_authority: Literal["none"] = "none"
    persona_evidence: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    send_enabled: Literal[False] = False


def seal_manifest(payload: dict[str, object]) -> ExecutiveManifest:
    """Seal the immutable manifest before it reaches the private mission store."""
    draft = cast(Any, ExecutiveManifest).model_construct(**payload, manifest_sha256="0" * 64)
    value = draft.model_dump(mode="json", exclude={"manifest_sha256"})
    value["manifest_sha256"] = canonical_sha256(value)
    return ExecutiveManifest.model_validate(value)


def seal_event(payload: dict[str, object]) -> ExecutiveEvent:
    """Seal a transition so state reconstruction rejects altered history."""
    draft = cast(Any, ExecutiveEvent).model_construct(**payload, event_sha256="0" * 64)
    value = draft.model_dump(mode="json", exclude={"event_sha256"})
    value["event_sha256"] = canonical_sha256(value)
    return ExecutiveEvent.model_validate(value)


def _require_digest(model: StrictModel, field: str) -> None:
    actual = getattr(model, field)
    expected = canonical_sha256(model.model_dump(mode="json", exclude={field}))
    if actual != expected:
        raise ValueError(f"{field} does not match its canonical payload")
