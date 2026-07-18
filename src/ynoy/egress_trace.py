from __future__ import annotations

from collections.abc import Mapping, Sequence

from ynoy.models import DataClass
from ynoy.models.formal_runtime import EgressLogicalEvent, EgressTrace
from ynoy.util import canonical_sha256


def build_egress_trace(
    *,
    observer_id: str,
    events: Sequence[EgressLogicalEvent],
) -> EgressTrace:
    """Seal the complete normalized observer projection, never raw private state."""
    ordered = tuple(events)
    draft = EgressTrace.model_construct(
        observer_id=observer_id,
        events=ordered,
        send_enabled=False,
        trace_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="python")
    payload["trace_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"trace_sha256"})
    )
    return EgressTrace.model_validate(payload)


def project_v1_private_trace(
    *,
    observer_id: str,
    private_state: Mapping[DataClass, object],
) -> EgressTrace:
    """V1 has no private egress path, so all admissible private states project identically."""
    if any(item == DataClass.PUBLIC_SYNTHETIC for item in private_state):
        raise ValueError("private-state projection accepts D1-D5 only")
    return build_egress_trace(observer_id=observer_id, events=())
