from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from ynoy.constants import (
    DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES,
    PERSONA_HOLDOUT_MAX_FILES,
    PERSONA_HOLDOUT_MAX_TOTAL_BYTES,
    PERSONA_HOLDOUT_MIN_FILES,
    PERSONA_STUDY_MAX_FILE_BYTES,
)
from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.models import DataClass, HoldoutSourceReceipt, ProtectedHoldoutFreeze
from ynoy.util import canonical_sha256, sha256_text


@dataclass(frozen=True, slots=True)
class HoldoutPlan:
    annotation_candidates: tuple[DiscoveredCodexFile, ...]
    holdout_sources: tuple[_LineageFile, ...]
    boundary_session_start_ns: int


@dataclass(frozen=True, slots=True)
class _LineageFile:
    item: DiscoveredCodexFile
    source_receipt: str
    thread_receipt: str
    parent_receipt: str | None
    session_start_ns: int
    component_receipt: str = ""


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, first: str, second: str) -> None:
        left, right = self.find(first), self.find(second)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


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
    annotation_components = {
        item.component_receipt
        for item in _component_lineages(tuple(_read_lineage(item) for item in annotation_files))
    }
    if annotation_receipts & {item.source_receipt for item in plan.holdout_sources}:
        raise DataValidationError(
            "persona_holdout_source_overlap", "An annotation source crossed into holdout."
        )
    if annotation_components & {item.component_receipt for item in plan.holdout_sources}:
        raise DataValidationError(
            "persona_holdout_lineage_overlap", "Explicit lineage crossed into holdout."
        )


def file_receipt(item: DiscoveredCodexFile) -> str:
    return canonical_sha256(
        (
            item.partition,
            item.relative.as_posix(),
            item.file_bytes,
            item.modified_ns,
            item.device,
            item.inode,
        )
    )


def session_start_ns(item: DiscoveredCodexFile) -> int:
    try:
        value = datetime.strptime(item.relative.name[8:27], "%Y-%m-%dT%H-%M-%S")
    except ValueError as exc:
        raise DataValidationError(
            "persona_holdout_filename_time_invalid",
            "A canonical rollout filename does not contain a valid session-start time.",
        ) from exc
    return int(value.replace(tzinfo=UTC).timestamp() * 1_000_000_000)


def _read_lineage(item: DiscoveredCodexFile) -> _LineageFile:
    with open_stable_codex_file(item) as stream:
        first = stream.readline(DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES + 1)
    if len(first) > DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES:
        raise DataValidationError(
            "persona_holdout_metadata_oversized", "A holdout metadata record exceeds its limit."
        )
    try:
        record = json.loads(first)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "persona_holdout_metadata_invalid", "A holdout metadata record is invalid."
        ) from exc
    if not isinstance(record, Mapping) or record.get("type") != "session_meta":
        raise DataValidationError(
            "persona_holdout_session_meta_required", "Holdout sources require session metadata."
        )
    payload = record.get("payload")
    metadata = payload if isinstance(payload, Mapping) else {}
    thread = metadata.get("id") or metadata.get("session_id")
    parent = metadata.get("parent_thread_id")
    if not isinstance(thread, str) or not thread:
        raise DataValidationError(
            "persona_holdout_thread_id_required", "Holdout lineage requires an opaque thread ID."
        )
    return _LineageFile(
        item,
        file_receipt(item),
        sha256_text(f"holdout-thread:{thread}"),
        sha256_text(f"holdout-thread:{parent}") if isinstance(parent, str) and parent else None,
        session_start_ns(item),
    )


def _component_lineages(values: tuple[_LineageFile, ...]) -> tuple[_LineageFile, ...]:
    graph = _UnionFind()
    known_threads = {value.thread_receipt for value in values}
    missing_parents = {
        value.parent_receipt
        for value in values
        if value.parent_receipt and value.parent_receipt not in known_threads
    }
    if missing_parents:
        raise DataValidationError(
            "persona_holdout_lineage_parent_missing",
            "A lineage parent is referenced but absent from the selected source set.",
        )
    for value in values:
        graph.find(value.thread_receipt)
        if value.parent_receipt:
            graph.union(value.thread_receipt, value.parent_receipt)
    groups: dict[str, list[str]] = defaultdict(list)
    for node in graph.parent:
        groups[graph.find(node)].append(node)
    receipts = {root: canonical_sha256(sorted(nodes)) for root, nodes in groups.items()}
    return tuple(
        _LineageFile(
            item=value.item,
            source_receipt=value.source_receipt,
            thread_receipt=value.thread_receipt,
            parent_receipt=value.parent_receipt,
            session_start_ns=value.session_start_ns,
            component_receipt=receipts[graph.find(value.thread_receipt)],
        )
        for value in values
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
