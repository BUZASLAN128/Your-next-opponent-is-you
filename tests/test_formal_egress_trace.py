from __future__ import annotations

from ynoy.egress_trace import project_v1_private_trace
from ynoy.models import DataClass


def test_private_state_does_not_change_external_trace() -> None:
    first = {data_class: object() for data_class in tuple(DataClass)[1:]}
    second = {data_class: object() for data_class in reversed(tuple(DataClass)[1:])}

    first_trace = project_v1_private_trace(observer_id="external-observer", private_state=first)
    second_trace = project_v1_private_trace(observer_id="external-observer", private_state=second)

    assert first_trace == second_trace
    assert first_trace.events == () and not first_trace.send_enabled
