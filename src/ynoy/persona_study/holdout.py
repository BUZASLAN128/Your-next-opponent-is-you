from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from ynoy.constants import (
    PERSONA_HOLDOUT_MAX_FILES,
    PERSONA_HOLDOUT_MAX_TOTAL_BYTES,
    PERSONA_HOLDOUT_MIN_FILES,
    PERSONA_STUDY_MAX_FILE_BYTES,
)
from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.errors import DataValidationError
from ynoy.models import DataClass, HoldoutSourceReceipt, ProtectedHoldoutFreeze
from ynoy.persona_study.lineage import LineageFile as _LineageFile
from ynoy.persona_study.lineage import component_lineages as _component_lineages
from ynoy.persona_study.lineage import (
    file_receipt,
    read_lineage,
    session_start_ns,
)
from ynoy.util import canonical_sha256

_read_lineage = read_lineage


@dataclass(frozen=True, slots=True)
class HoldoutPlan:
    annotation_candidates: tuple[DiscoveredCodexFile, ...]
    holdout_sources: tuple[_LineageFile, ...]
    boundary_session_start_ns: int


def plan_protected_holdout(
    files: tuple[DiscoveredCodexFile, ...], *, stable_before: datetime | None
) -> HoldoutPlan:
    stable_ns = None if stable_before is None else int(stable_before.timestamp() * 1_000_000_000)
    eligible = tuple(
        item
        for item in files
        if 0 < item.file_bytes <= PERSONA_STUDY_MAX_FILE_BYTES
        if stable_ns is None or item.modified_ns <= stable_ns
    )
    lineages = _component_lineages(tuple(_read_lineage(item) for item in eligible))
    groups: dict[str, list[_LineageFile]] = defaultdict(list)
    for lineage in lineages:
        groups[lineage.component_receipt].append(lineage)
    ordered = sorted(groups.values(), key=_component_time_key, reverse=True)
    selected = _select_holdout_groups(ordered)
    boundary = min(item.session_start_ns for item in selected)
    selected_components = {item.component_receipt for item in selected}
    annotation = tuple(
        item.item
        for item in lineages
        if item.component_receipt not in selected_components and item.session_start_ns < boundary
    )
    if len(annotation) < 24:
        raise DataValidationError(
            "persona_holdout_annotation_history_insufficient",
            "A protected temporal holdout leaves fewer than 24 earlier annotation files.",
        )
    return HoldoutPlan(annotation, tuple(selected), boundary)


def build_protected_holdout(
    plan: HoldoutPlan,
    annotation_files: tuple[DiscoveredCodexFile, ...],
    annotation_selection_sha256: str,
    *,
    created_at: datetime,
    data_class: DataClass,
) -> ProtectedHoldoutFreeze:
    _validate_disjoint(plan, annotation_files)
    sources = tuple(
        HoldoutSourceReceipt(
            source_receipt=item.source_receipt,
            lineage_component_receipt=item.component_receipt,
            partition=item.item.partition,
            file_bytes=item.item.file_bytes,
            session_start_ns=item.session_start_ns,
        )
        for item in sorted(plan.holdout_sources, key=lambda value: value.source_receipt)
    )
    freeze_id = canonical_sha256(
        {
            "protocol": "persona-holdout-freeze/0.1",
            "annotation": annotation_selection_sha256,
            "sources": [item.model_dump(mode="json") for item in sources],
        }
    )
    payload = {
        "freeze_id": freeze_id,
        "created_at": created_at,
        "annotation_selection_sha256": annotation_selection_sha256,
        "annotation_max_session_start_ns": max(session_start_ns(item) for item in annotation_files),
        "boundary_session_start_ns": plan.boundary_session_start_ns,
        "sources": sources,
        "selected_file_count": len(sources),
        "selected_input_bytes": sum(item.file_bytes for item in sources),
        "source_data_class": data_class,
    }
    draft = cast(Any, ProtectedHoldoutFreeze).model_construct(**payload, freeze_sha256="0" * 64)
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"freeze_sha256"}))
    return ProtectedHoldoutFreeze.model_validate({**payload, "freeze_sha256": digest})


def _validate_disjoint(
    plan: HoldoutPlan, annotation_files: tuple[DiscoveredCodexFile, ...]
) -> None:
    annotation_receipts = {file_receipt(item) for item in annotation_files}
    holdout_receipts = {item.source_receipt for item in plan.holdout_sources}
    if annotation_receipts & holdout_receipts:
        raise DataValidationError(
            "persona_holdout_source_overlap", "An annotation source crossed into holdout."
        )
    combined = _component_lineages(
        tuple(
            _read_lineage(item)
            for item in (*annotation_files, *(source.item for source in plan.holdout_sources))
        )
    )
    component_by_source = {item.source_receipt: item.component_receipt for item in combined}
    if (annotation_receipts | holdout_receipts) - component_by_source.keys():
        raise DataValidationError(
            "persona_holdout_plan_binding_invalid",
            "A holdout plan source no longer matches its canonical metadata binding.",
        )
    if any(
        source.component_receipt != component_by_source[source.source_receipt]
        for source in plan.holdout_sources
    ):
        raise DataValidationError(
            "persona_holdout_plan_binding_invalid",
            "A holdout plan lineage component no longer matches its source closure.",
        )
    annotation_components = {component_by_source[receipt] for receipt in annotation_receipts}
    holdout_components = {component_by_source[receipt] for receipt in holdout_receipts}
    if annotation_components & holdout_components:
        raise DataValidationError(
            "persona_holdout_lineage_overlap", "Explicit lineage crossed into holdout."
        )


def _select_holdout_groups(groups: list[list[_LineageFile]]) -> list[_LineageFile]:
    selected: list[_LineageFile] = []
    total_bytes = 0
    for group in groups:
        group_bytes = sum(item.item.file_bytes for item in group)
        if len(selected) + len(group) > PERSONA_HOLDOUT_MAX_FILES:
            continue
        if total_bytes + group_bytes > PERSONA_HOLDOUT_MAX_TOTAL_BYTES:
            continue
        selected.extend(group)
        total_bytes += group_bytes
        if len(selected) >= PERSONA_HOLDOUT_MIN_FILES:
            break
    if len(selected) < PERSONA_HOLDOUT_MIN_FILES:
        raise DataValidationError(
            "persona_holdout_source_insufficient",
            "The bounded source cannot freeze eight protected holdout files.",
        )
    return selected


def _component_time_key(group: list[_LineageFile]) -> tuple[int, int, str]:
    return (
        min(item.session_start_ns for item in group),
        max(item.session_start_ns for item in group),
        canonical_sha256(sorted(item.source_receipt for item in group)),
    )
