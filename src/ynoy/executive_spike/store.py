from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.executive_spike.contracts import (
    ExecutiveEvent,
    ExecutiveManifest,
    PlannerKind,
    seal_event,
    seal_manifest,
)
from ynoy.full_persona.run_lock import exclusive_run_lock
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes, new_id, utc_now


class ExecutiveSpikeStore:
    """Private immutable event-chain store for the D0 synthetic executive spike."""

    def __init__(self, private_root: Path) -> None:
        assessment = require_private_root(private_root, real_data=False)
        self.root = assessment.root / "executive-spikes"
        reject_link_if_present(self.root)

    def create(
        self, mission: str, *, planner_kind: PlannerKind, model_identity: str | None
    ) -> ExecutiveManifest:
        """Allocate one mission directory and immutable manifest without overwriting."""
        manifest = seal_manifest(
            {
                "mission_id": new_id(),
                "mission": mission,
                "created_at": utc_now(),
                "planner_kind": planner_kind,
                "model_identity": model_identity,
            }
        )
        root = self.mission_root(manifest.mission_id)
        if root.exists():
            raise DataValidationError("executive_mission_exists", "Mission already exists.")
        (root / "events").mkdir(parents=True)
        atomic_write_bytes(
            root / "manifest.json", canonical_json_bytes(manifest.model_dump(mode="json"))
        )
        return manifest

    def manifest(self, mission_id: UUID) -> ExecutiveManifest:
        """Load the immutable manifest after bounded validation."""
        try:
            return ExecutiveManifest.model_validate_json(
                _read(self.mission_root(mission_id) / "manifest.json")
            )
        except (OSError, ValidationError) as exc:
            raise DataValidationError(
                "executive_manifest_invalid", "Mission manifest is invalid."
            ) from exc

    def append(
        self, mission_id: UUID, kind: str, summary: str, workspace_sha256: str
    ) -> ExecutiveEvent:
        """Append exactly one chained event under the per-mission OS lock."""
        root = self.mission_root(mission_id)
        with exclusive_run_lock(root / "mission.lock"):
            events = self.events(mission_id)
            if len(events) >= 32:
                raise DataValidationError(
                    "executive_event_budget_exhausted", "Mission event budget is exhausted."
                )
            event = seal_event(
                {
                    "mission_id": mission_id,
                    "revision": len(events) + 1,
                    "kind": kind,
                    "summary": summary,
                    "workspace_sha256": workspace_sha256,
                    "previous_event_sha256": events[-1].event_sha256 if events else None,
                    "created_at": utc_now(),
                }
            )
            atomic_write_bytes(
                root / "events" / f"{event.revision:08d}.json",
                canonical_json_bytes(event.model_dump(mode="json")),
            )
        return event

    def events(self, mission_id: UUID) -> tuple[ExecutiveEvent, ...]:
        """Read every immutable event and fail closed on gaps, reordering, or tampering."""
        root = self.mission_root(mission_id)
        events_path = root / "events"
        reject_link_if_present(root)
        reject_link_if_present(events_path)
        if not events_path.is_dir():
            raise DataValidationError("executive_events_missing", "Mission events are missing.")
        events = tuple(_event(path) for path in sorted(events_path.glob("*.json")))
        _validate_chain(mission_id, events)
        return events

    def mission_root(self, mission_id: UUID) -> Path:
        """Resolve a generated mission path; callers cannot supply arbitrary descendants."""
        return self.root / str(mission_id)


def _event(path: Path) -> ExecutiveEvent:
    try:
        return ExecutiveEvent.model_validate_json(_read(path))
    except (OSError, ValidationError) as exc:
        raise DataValidationError("executive_event_invalid", "Mission event is invalid.") from exc


def _read(path: Path) -> bytes:
    require_regular_file(path)
    value = path.read_bytes()
    if len(value) > 16 * 1024:
        raise DataValidationError("executive_record_oversized", "Mission record is oversized.")
    return value


def _validate_chain(mission_id: UUID, events: tuple[ExecutiveEvent, ...]) -> None:
    for index, event in enumerate(events, start=1):
        previous = events[index - 2].event_sha256 if index > 1 else None
        if (
            event.mission_id != mission_id
            or event.revision != index
            or event.previous_event_sha256 != previous
        ):
            raise DataValidationError(
                "executive_event_chain_invalid", "Mission event chain is invalid."
            )
