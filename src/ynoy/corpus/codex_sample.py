from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from ynoy.corpus.codex import assert_synthetic_codex_root
from ynoy.corpus.codex_discovery import (
    CodexInventoryLimits,
    DiscoveredCodexFile,
    discover_codex_sessions,
    resolve_codex_root,
)
from ynoy.corpus.codex_sample_reader import (
    CodexContentPilotLimits,
    ParsedCodexSampleFile,
    parse_codex_sample_file,
)
from ynoy.errors import DataValidationError
from ynoy.models import CodexContentPilotSummary, DataClass, SourceEvent
from ynoy.util import canonical_sha256

SizeBucket = Literal["small", "medium", "large"]


@dataclass(frozen=True, slots=True)
class CodexContentSample:
    summary: CodexContentPilotSummary
    events: tuple[SourceEvent, ...]


@dataclass(frozen=True, slots=True)
class _SelectedFile:
    item: DiscoveredCodexFile
    bucket: SizeBucket


class CodexContentSampleAdapter:
    """Run a bounded Codex dialogue parser without persisting or deriving identity."""

    name = "codex_local_content_pilot"

    def __init__(self, limits: CodexContentPilotLimits | None = None):
        self.limits = limits or CodexContentPilotLimits()

    def sample(self, root: Path, *, synthetic: bool) -> CodexContentSample:
        source = resolve_codex_root(root)
        if synthetic:
            assert_synthetic_codex_root(source)
        discovery_limits = CodexInventoryLimits(max_first_record_bytes=self.limits.max_line_bytes)
        discovery = discover_codex_sessions(source, discovery_limits)
        selected = _select_files(discovery.files, self.limits)
        namespace = _selection_namespace(selected)
        import_run_id = uuid5(NAMESPACE_URL, f"codex-content-pilot:{namespace}")
        data_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS
        parsed = _parse_selected(selected, namespace, import_run_id, data_class, self.limits)
        events = tuple(event for item in parsed for event in item.events)
        summary = _summary(selected, parsed, events, data_class, synthetic, self.limits)
        return CodexContentSample(summary, events)


def _select_files(
    files: tuple[DiscoveredCodexFile, ...], limits: CodexContentPilotLimits
) -> tuple[_SelectedFile, ...]:
    eligible = [
        _SelectedFile(item, bucket)
        for item in files
        if 0 < item.file_bytes <= limits.max_file_bytes
        if (bucket := _size_bucket(item.file_bytes)) is not None
    ]
    groups = (
        [item for item in eligible if item.item.partition == "sessions" and item.bucket == "small"],
        [
            item
            for item in eligible
            if item.item.partition == "archived_sessions" and item.bucket == "small"
        ],
        [
            item
            for item in eligible
            if item.item.partition == "sessions" and item.bucket == "medium"
        ],
        [
            item
            for item in eligible
            if item.item.partition == "archived_sessions" and item.bucket == "medium"
        ],
        [item for item in eligible if item.bucket == "large"],
    )
    selected: list[_SelectedFile] = []
    for group in groups:
        _append_if_bounded(selected, _middle(group), limits)
    for candidate in sorted(eligible, key=_selection_key):
        _append_if_bounded(selected, candidate, limits)
    if not selected:
        raise DataValidationError(
            "codex_pilot_no_eligible_files", "No canonical Codex file fits the pilot limits."
        )
    return tuple(selected)


def _append_if_bounded(
    selected: list[_SelectedFile],
    candidate: _SelectedFile | None,
    limits: CodexContentPilotLimits,
) -> None:
    if candidate is None or candidate in selected or len(selected) >= limits.max_files:
        return
    selected_bytes = sum(item.item.file_bytes for item in selected)
    if selected_bytes + candidate.item.file_bytes <= limits.max_total_input_bytes:
        selected.append(candidate)


def _middle(items: list[_SelectedFile]) -> _SelectedFile | None:
    ordered = sorted(items, key=_selection_key)
    return ordered[len(ordered) // 2] if ordered else None


def _selection_key(item: _SelectedFile) -> tuple[object, ...]:
    return item.item.file_bytes, item.item.partition, item.item.relative.as_posix()


def _size_bucket(size: int) -> SizeBucket | None:
    if size < 256 * 1024:
        return "small"
    if size < 1024 * 1024:
        return "medium"
    if size <= 4 * 1024**2:
        return "large"
    return None


def _selection_namespace(selected: tuple[_SelectedFile, ...]) -> str:
    return canonical_sha256(
        [
            {
                "partition": value.item.partition,
                "relative": value.item.relative.as_posix(),
                "bytes": value.item.file_bytes,
                "modified_ns": value.item.modified_ns,
                "device": value.item.device,
                "inode": value.item.inode,
            }
            for value in selected
        ]
    )


def _parse_selected(
    selected: tuple[_SelectedFile, ...],
    namespace: str,
    import_run_id: UUID,
    data_class: DataClass,
    limits: CodexContentPilotLimits,
) -> tuple[ParsedCodexSampleFile, ...]:
    parsed: list[ParsedCodexSampleFile] = []
    records = events = 0
    for value in selected:
        result = parse_codex_sample_file(
            value.item,
            namespace=namespace,
            import_run_id=import_run_id,
            source_data_class=data_class,
            limits=limits,
            remaining_records=limits.max_records - records,
            remaining_events=limits.max_events - events,
        )
        parsed.append(result)
        records += result.record_count
        events += len(result.events)
    return tuple(parsed)


def _summary(
    selected: tuple[_SelectedFile, ...],
    parsed: tuple[ParsedCodexSampleFile, ...],
    events: tuple[SourceEvent, ...],
    data_class: DataClass,
    synthetic: bool,
    limits: CodexContentPilotLimits,
) -> CodexContentPilotSummary:
    record_types = _merge_counts(item.record_type_counts for item in parsed)
    excluded = _merge_counts(item.excluded_counts for item in parsed)
    source_kinds = Counter(str(item.metadata["source_kind"]) for item in events)
    speakers = Counter(item.speaker.value for item in events)
    repeats = Counter(str(item.metadata["repeat_cluster_key"]) for item in events)
    snapshot = _normalized_snapshot(parsed, events)
    return CodexContentPilotSummary(
        source_data_class=data_class,
        synthetic=synthetic,
        selected_file_count=len(selected),
        selected_input_bytes=sum(item.item.file_bytes for item in selected),
        scanned_record_count=sum(item.record_count for item in parsed),
        normalized_event_count=len(events),
        selected_partition_counts=dict(
            sorted(Counter(item.item.partition for item in selected).items())
        ),
        selected_bucket_counts=dict(sorted(Counter(item.bucket for item in selected).items())),
        record_type_counts=record_types,
        source_kind_counts=dict(sorted(source_kinds.items())),
        speaker_counts=dict(sorted(speakers.items())),
        excluded_counts=excluded,
        repeated_content_cluster_count=sum(count > 1 for count in repeats.values()),
        explicit_parent_thread_count=sum(item.explicit_parent_thread for item in parsed),
        max_files=limits.max_files,
        max_total_input_bytes=limits.max_total_input_bytes,
        max_file_bytes=limits.max_file_bytes,
        max_line_bytes=limits.max_line_bytes,
        max_records=limits.max_records,
        max_events=limits.max_events,
        max_content_bytes=limits.max_content_bytes,
        normalized_snapshot_sha256=snapshot,
    )


def _merge_counts(values: Iterable[dict[str, int]]) -> dict[str, int]:
    total: Counter[str] = Counter()
    for value in values:
        total.update(value)
    return dict(sorted(total.items()))


def _normalized_snapshot(
    parsed: tuple[ParsedCodexSampleFile, ...], events: tuple[SourceEvent, ...]
) -> str:
    file_digests = [item.source_digest for item in parsed]
    event_receipts = [
        {
            "source_id": item.source_id,
            "event_id": item.event_id,
            "speaker": item.speaker.value,
            "content_sha256": item.content_sha256,
            "metadata": item.metadata,
        }
        for item in events
    ]
    return canonical_sha256({"files": file_digests, "events": event_receipts})
