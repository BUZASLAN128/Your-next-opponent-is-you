from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Literal

from ynoy.errors import DataValidationError
from ynoy.models import EvidenceWindow

Split = Literal["annotation_development", "annotation_reserved"]


def chronological_split(
    windows: tuple[EvidenceWindow, ...],
) -> tuple[dict[str, Split], datetime]:
    groups: dict[str, list[EvidenceWindow]] = defaultdict(list)
    for window in windows:
        groups[window.dependency_component_id].append(window)
    ordered = sorted(groups.values(), key=_component_time_key)
    candidates: list[tuple[int, int, datetime]] = []
    for index in range(1, len(ordered)):
        dev, holdout = ordered[:index], ordered[index:]
        dev_times = [item.focus.event_time for group in dev for item in group]
        holdout_times = [item.focus.event_time for group in holdout for item in group]
        if None in dev_times or None in holdout_times:
            continue
        cutoff = max(item for item in dev_times if item is not None)
        if cutoff < min(item for item in holdout_times if item is not None):
            candidates.append((abs(sum(map(len, dev)) - 12), index, cutoff))
    if not candidates:
        raise DataValidationError(
            "persona_study_temporal_split_unavailable",
            "No contamination-safe chronological component split exists.",
        )
    _, boundary, cutoff = min(candidates)
    development = {item.window_id for group in ordered[:boundary] for item in group}
    split: dict[str, Split] = {
        item.window_id: (
            "annotation_development" if item.window_id in development else "annotation_reserved"
        )
        for item in windows
    }
    return split, cutoff


def _component_time_key(group: list[EvidenceWindow]) -> tuple[datetime, str]:
    times = [item.focus.event_time for item in group]
    if any(item is None for item in times):
        raise DataValidationError("persona_study_time_missing", "A study window lacks event time.")
    return min(item for item in times if item is not None), group[0].dependency_component_id
