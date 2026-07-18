from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ynoy.errors import PolicyViolation
from ynoy.models.formal_erasure import ErasureTombstone
from ynoy.util import new_id


@dataclass(frozen=True, slots=True)
class FutureTraceEvent:
    schedule: str
    judgment: str = "unavailable"
    retrieval: str = "empty"
    derivation: str = "blocked_tombstone"
    log_class: str = "erasure_fence_denial"
    telemetry_class: str = "no_private_payload"
    external_calls: int = 0


class SyntheticErasureStore:
    """In-memory protocol proof only; it is not the persistent V1 fence."""

    def __init__(self, *, registry_version: str) -> None:
        self.registry_version = registry_version
        self._records: dict[UUID, set[UUID]] = {}
        self._tombstones: dict[UUID, ErasureTombstone] = {}

    def ingest(self, source_id: UUID) -> None:
        self._assert_not_tombstoned(source_id)
        self._records.setdefault(source_id, set())

    def create_derivative(self, source_id: UUID, derivative_id: UUID) -> None:
        self._assert_not_tombstoned(source_id)
        if source_id not in self._records:
            raise PolicyViolation("erasure_source_unavailable", "Source is unavailable.")
        self._records[source_id].add(derivative_id)

    def delete(self, source_id: UUID, *, revision: int) -> ErasureTombstone:
        self._records.pop(source_id, None)
        tombstone = ErasureTombstone(
            tombstone_id=new_id(),
            opaque_source_id=source_id,
            registry_version=self.registry_version,
            deleted_at_revision=revision,
        )
        self._tombstones[source_id] = tombstone
        return tombstone

    def future_trace(
        self,
        source_id: UUID,
        *,
        schedules: tuple[str, ...],
        counterfactual_private_state: object,
    ) -> tuple[FutureTraceEvent, ...]:
        del counterfactual_private_state
        self._assert_tombstoned(source_id)
        return tuple(FutureTraceEvent(schedule=item) for item in schedules)

    def _assert_not_tombstoned(self, source_id: UUID) -> None:
        if source_id in self._tombstones:
            raise PolicyViolation(
                "erasure_tombstone_fence", "A deleted source cannot be recreated or derived."
            )

    def _assert_tombstoned(self, source_id: UUID) -> None:
        if source_id not in self._tombstones:
            raise PolicyViolation("erasure_fence_missing", "No erasure fence exists for source.")
