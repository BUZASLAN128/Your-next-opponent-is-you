from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from ynoy.constants import (
    PERSONA_STUDY_MAX_EVENTS,
    PERSONA_STUDY_MAX_FILE_BYTES,
    PERSONA_STUDY_MAX_FILES,
    PERSONA_STUDY_MAX_RECORDS,
    PERSONA_STUDY_MAX_TOTAL_BYTES,
    PERSONA_STUDY_STABILITY_MINUTES,
)
from ynoy.corpus.codex import assert_synthetic_codex_root
from ynoy.corpus.codex_discovery import (
    CodexInventoryLimits,
    DiscoveredCodexFile,
    discover_codex_sessions,
    resolve_codex_root,
)
from ynoy.corpus.codex_sample_reader import CodexContentPilotLimits, parse_codex_sample_file
from ynoy.errors import DataValidationError
from ynoy.models import DataClass, ProtectedHoldoutFreeze, SourceEvent
from ynoy.persona_study.holdout import (
    build_protected_holdout,
    plan_protected_holdout,
)
from ynoy.persona_study.lineage import file_receipt, session_start_ns
from ynoy.util import canonical_sha256


@dataclass(frozen=True, slots=True)
class StudySourceSample:
    events: tuple[SourceEvent, ...]
    source_snapshot_sha256: str
    selected_file_count: int
    selected_input_bytes: int
    scanned_record_count: int
    selected_file_receipts: tuple[str, ...]
    selected_max_session_start_ns: int


@dataclass(frozen=True, slots=True)
class _StudyFile:
    item: DiscoveredCodexFile
    bucket: str


def load_study_source(
    root: Path, *, synthetic: bool, evaluation_time: datetime | None = None
) -> StudySourceSample:
    source = resolve_codex_root(root)
    if synthetic:
        assert_synthetic_codex_root(source)
    limits = _limits()
    discovery = discover_codex_sessions(
        source, CodexInventoryLimits(max_first_record_bytes=limits.max_line_bytes)
    )
    selected = _select_files(
        discovery.files,
        stable_before=None
        if synthetic or evaluation_time is None
        else evaluation_time - timedelta(minutes=PERSONA_STUDY_STABILITY_MINUTES),
    )
    return _load_selected(selected, synthetic=synthetic)


def load_protected_study_source(
    root: Path, *, synthetic: bool, evaluation_time: datetime
) -> tuple[StudySourceSample, ProtectedHoldoutFreeze]:
    source = resolve_codex_root(root)
    if synthetic:
        assert_synthetic_codex_root(source)
    limits = _limits()
    discovery = discover_codex_sessions(
        source, CodexInventoryLimits(max_first_record_bytes=limits.max_line_bytes)
    )
    stable_before = (
        None if synthetic else evaluation_time - timedelta(minutes=PERSONA_STUDY_STABILITY_MINUTES)
    )
    plan = plan_protected_holdout(discovery.files, stable_before=stable_before)
    selected = _select_files(plan.annotation_candidates, stable_before=None)
    sample = _load_selected(selected, synthetic=synthetic)
    freeze = build_protected_holdout(
        plan,
        tuple(item.item for item in selected),
        _selection_namespace(selected),
        created_at=evaluation_time,
        data_class=DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS,
    )
    return sample, freeze


def _load_selected(selected: tuple[_StudyFile, ...], *, synthetic: bool) -> StudySourceSample:
    limits = _limits()
    namespace = _selection_namespace(selected)
    import_id = uuid5(NAMESPACE_URL, f"persona-study:{namespace}")
    data_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS
    events, records, digests = _parse_files(selected, namespace, import_id, data_class, limits)
    snapshot = canonical_sha256(
        {
            "files": digests,
            "events": [
                (item.event_id, item.content_sha256, item.conversation_id, item.event_time)
                for item in events
            ],
        }
    )
    return StudySourceSample(
        events,
        snapshot,
        len(selected),
        sum(item.item.file_bytes for item in selected),
        records,
        tuple(sorted(file_receipt(item.item) for item in selected)),
        max(session_start_ns(item.item) for item in selected),
    )


def _limits() -> CodexContentPilotLimits:
    return CodexContentPilotLimits(
        max_files=PERSONA_STUDY_MAX_FILES,
        max_total_input_bytes=PERSONA_STUDY_MAX_TOTAL_BYTES,
        max_file_bytes=PERSONA_STUDY_MAX_FILE_BYTES,
        max_records=PERSONA_STUDY_MAX_RECORDS,
        max_events=PERSONA_STUDY_MAX_EVENTS,
    )


def _select_files(
    files: tuple[DiscoveredCodexFile, ...], *, stable_before: datetime | None
) -> tuple[_StudyFile, ...]:
    stable_ns = None if stable_before is None else int(stable_before.timestamp() * 1_000_000_000)
    eligible = [
        _StudyFile(item, bucket)
        for item in files
        if 0 < item.file_bytes <= PERSONA_STUDY_MAX_FILE_BYTES
        if stable_ns is None or item.modified_ns <= stable_ns
        if (bucket := _size_bucket(item.file_bytes)) is not None
    ]
    groups: dict[tuple[str, str], list[_StudyFile]] = defaultdict(list)
    for item in eligible:
        groups[(item.item.partition, item.bucket)].append(item)
    preferred: list[_StudyFile] = []
    for key in sorted(groups):
        ordered = sorted(groups[key], key=_temporal_key)
        preferred.extend(_quantiles(ordered, 4))
    remaining = sorted((item for item in eligible if item not in preferred), key=_fallback_key)
    selected = _bounded_unique((*preferred, *remaining))
    if len(selected) != PERSONA_STUDY_MAX_FILES:
        raise DataValidationError(
            "persona_study_source_insufficient",
            "The bounded source sample cannot provide 24 canonical files.",
        )
    return tuple(selected)


def _bounded_unique(candidates: tuple[_StudyFile, ...]) -> list[_StudyFile]:
    selected: list[_StudyFile] = []
    total = 0
    for candidate in candidates:
        if candidate in selected or len(selected) >= PERSONA_STUDY_MAX_FILES:
            continue
        if total + candidate.item.file_bytes > PERSONA_STUDY_MAX_TOTAL_BYTES:
            continue
        selected.append(candidate)
        total += candidate.item.file_bytes
    return selected


def _quantiles(items: list[_StudyFile], count: int) -> list[_StudyFile]:
    if len(items) <= count:
        return items
    indexes = {round((index + 0.5) * (len(items) - 1) / count) for index in range(count)}
    return [items[index] for index in sorted(indexes)]


def _size_bucket(size: int) -> str | None:
    if size < 256 * 1024:
        return "small"
    if size < 1024 * 1024:
        return "medium"
    return "large" if size <= PERSONA_STUDY_MAX_FILE_BYTES else None


def _temporal_key(item: _StudyFile) -> tuple[int, str]:
    return item.item.modified_ns, item.item.relative.as_posix()


def _fallback_key(item: _StudyFile) -> tuple[str, int, int, str]:
    return (
        item.item.partition,
        item.item.file_bytes,
        item.item.modified_ns,
        item.item.relative.as_posix(),
    )


def _selection_namespace(selected: tuple[_StudyFile, ...]) -> str:
    return canonical_sha256(
        [
            (
                item.item.partition,
                item.item.relative.as_posix(),
                item.item.file_bytes,
                item.item.modified_ns,
            )
            for item in selected
        ]
    )


def _parse_files(
    selected: tuple[_StudyFile, ...],
    namespace: str,
    import_id: UUID,
    data_class: DataClass,
    limits: CodexContentPilotLimits,
) -> tuple[tuple[SourceEvent, ...], int, tuple[str, ...]]:
    events: list[SourceEvent] = []
    digests: list[str] = []
    records = 0
    for value in selected:
        parsed = parse_codex_sample_file(
            value.item,
            namespace=namespace,
            import_run_id=import_id,
            source_data_class=data_class,
            limits=limits,
            remaining_records=limits.max_records - records,
            remaining_events=limits.max_events - len(events),
        )
        events.extend(parsed.events)
        digests.append(parsed.source_digest)
        records += parsed.record_count
    return tuple(events), records, tuple(digests)
