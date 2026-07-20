from __future__ import annotations

from typing import Any


def assert_static_predictions_safe(static: tuple[Any, ...], split: Any) -> None:
    history_ids = {item.evidence_id for item in split.history}
    assert tuple(item.case_id for item in static) == split.manifest.sealed_case_ids
    assert all(item.target_seen is False for item in static)
    assert all(set(item.evidence_ids).issubset(history_ids) for item in static)
    assert any(not item.abstained for item in static)
