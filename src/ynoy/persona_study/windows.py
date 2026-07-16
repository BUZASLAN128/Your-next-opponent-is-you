from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, cast

from ynoy.errors import DataValidationError
from ynoy.models import (
    ClaimHolder,
    EvidenceWindow,
    SourceEvent,
    Speaker,
    StudyMessage,
)
from ynoy.models.persona_study import AnnotationPresentation, BlindMapEntry
from ynoy.persona_study.heuristics import (
    challenge_tags,
    inert_control_like,
    meaningful_repeat,
)
from ynoy.persona_study.presentations import build_presentations
from ynoy.persona_study.splitting import chronological_split
from ynoy.util import canonical_sha256, sha256_text


@dataclass(frozen=True, slots=True)
class PreparedWindows:
    study_id: str
    windows: tuple[EvidenceWindow, ...]
    presentations: tuple[AnnotationPresentation, ...]
    blind_map: tuple[BlindMapEntry, ...]
    cutoff: datetime
    selection_sha256: str
    blind_map_sha256: str
    dependency_component_count: int
    annotation_development_count: int
    annotation_reserved_count: int


@dataclass(frozen=True, slots=True)
class _Candidate:
    focus: SourceEvent
    context: tuple[SourceEvent, ...]
    tags: tuple[str, ...]
    component_id: str = ""


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


def prepare_windows(events: tuple[SourceEvent, ...], source_snapshot: str) -> PreparedWindows:
    candidates = _candidate_windows(events)
    if len(candidates) < 24:
        raise DataValidationError(
            "persona_study_windows_insufficient",
            "The bounded source sample cannot provide 24 contextual user windows.",
        )
    component_ids = _component_ids(events)
    candidates = tuple(
        replace(item, component_id=component_ids[item.focus.conversation_id]) for item in candidates
    )
    selected = _select_candidates(candidates, source_snapshot)
    windows = tuple(_materialize(item, source_snapshot) for item in selected)
    split, cutoff = chronological_split(windows)
    selection_sha = canonical_sha256(
        [(item.window_id, item.window_sha256, split[item.window_id]) for item in windows]
    )
    study_id = canonical_sha256(
        {"protocol": "persona-study/0.1", "source": source_snapshot, "selection": selection_sha}
    )
    presentations, blind_map = build_presentations(windows, split, study_id)
    component_count = len({item.dependency_component_id for item in windows})
    return PreparedWindows(
        study_id,
        windows,
        presentations,
        blind_map,
        cutoff,
        selection_sha,
        canonical_sha256([item.model_dump(mode="json") for item in blind_map]),
        component_count,
        sum(value == "annotation_development" for value in split.values()),
        sum(value == "annotation_reserved" for value in split.values()),
    )


def _candidate_windows(events: tuple[SourceEvent, ...]) -> tuple[_Candidate, ...]:
    grouped: dict[str, list[SourceEvent]] = defaultdict(list)
    exact_counts = Counter(
        str(event.metadata.get("global_exact_content_key", ""))
        for event in events
        if event.speaker == Speaker.USER
    )
    for event in events:
        grouped[event.conversation_id].append(event)
    candidates: list[_Candidate] = []
    seen_exact: set[str] = set()
    for conversation in sorted(grouped):
        ordered = sorted(grouped[conversation], key=_sequence_key)
        for index, event in enumerate(ordered):
            exact_key = str(event.metadata.get("global_exact_content_key", ""))
            context = tuple(ordered[max(0, index - 4) : index])
            if not _eligible_focus(event, context, exact_key, seen_exact, exact_counts[exact_key]):
                continue
            seen_exact.add(exact_key)
            candidates.append(_Candidate(event, context, challenge_tags(event.content)))
    return tuple(candidates)


def _eligible_focus(
    event: SourceEvent,
    context: tuple[SourceEvent, ...],
    exact_key: str,
    seen_exact: set[str],
    exact_count: int,
) -> bool:
    return bool(
        event.speaker == Speaker.USER
        and event.claim_holder == ClaimHolder.UNKNOWN
        and event.event_time is not None
        and context
        and exact_key
        and exact_key not in seen_exact
        and (exact_count == 1 or meaningful_repeat(event.content))
        and not inert_control_like(event.content)
    )


def _select_candidates(
    candidates: tuple[_Candidate, ...], source_snapshot: str
) -> tuple[_Candidate, ...]:
    challenge_pool = sorted(
        (item for item in candidates if item.tags),
        key=lambda item: (-len(item.tags), _stable_key(item, source_snapshot)),
    )
    challenge = _diverse_challenge(challenge_pool, 12)
    excluded = {item.focus.event_id for item in challenge}
    remaining = sorted(
        (item for item in candidates if item.focus.event_id not in excluded),
        key=lambda item: _temporal_key(item, source_snapshot),
    )
    sampled = tuple(replace(item, tags=()) for item in _diverse_components(remaining, 12))
    if len(challenge) != 12 or len(sampled) != 12:
        raise DataValidationError(
            "persona_study_arms_insufficient", "Both persona-study arms require 12 windows."
        )
    return tuple((*sampled, *challenge))


def _diverse_challenge(candidates: list[_Candidate], count: int) -> tuple[_Candidate, ...]:
    selected: list[_Candidate] = []
    covered: set[str] = set()
    components: set[str] = set()
    for candidate in candidates:
        if len(selected) >= count:
            break
        if (
            any(tag not in covered for tag in candidate.tags)
            or candidate.component_id not in components
        ):
            selected.append(candidate)
            covered.update(candidate.tags)
            components.add(candidate.component_id)
    for candidate in candidates:
        if len(selected) >= count:
            break
        if candidate not in selected:
            selected.append(candidate)
    return tuple(selected)


def _diverse_components(candidates: list[_Candidate], count: int) -> tuple[_Candidate, ...]:
    representatives: list[_Candidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.component_id not in seen:
            representatives.append(candidate)
            seen.add(candidate.component_id)
    selected = list(_spread(representatives, count))
    for candidate in _spread(candidates, len(candidates)):
        if len(selected) >= count:
            break
        if candidate not in selected:
            selected.append(candidate)
    return tuple(selected[:count])


def _spread(candidates: list[_Candidate], count: int) -> tuple[_Candidate, ...]:
    if len(candidates) < count:
        return tuple(candidates)
    indexes = {round((index + 0.5) * (len(candidates) - 1) / count) for index in range(count)}
    selected = [candidates[index] for index in sorted(indexes)]
    for candidate in candidates:
        if len(selected) >= count:
            break
        if candidate not in selected:
            selected.append(candidate)
    return tuple(selected[:count])


def _component_ids(events: tuple[SourceEvent, ...]) -> dict[str, str]:
    graph = _UnionFind()
    for event in events:
        conversation = f"thread:{event.conversation_id}"
        graph.find(conversation)
        parent = event.metadata.get("thread_parent_key")
        if isinstance(parent, str) and parent:
            graph.union(conversation, f"thread:{parent}")
        repeat = event.metadata.get("global_exact_content_key")
        if (
            event.speaker == Speaker.USER
            and isinstance(repeat, str)
            and repeat
            and meaningful_repeat(event.content)
            and not inert_control_like(event.content)
        ):
            graph.union(conversation, f"exact:{repeat}")
    groups: dict[str, list[str]] = defaultdict(list)
    for node in graph.parent:
        groups[graph.find(node)].append(node)
    digests = {root: canonical_sha256(sorted(nodes)) for root, nodes in groups.items()}
    return {
        event.conversation_id: digests[graph.find(f"thread:{event.conversation_id}")]
        for event in events
    }


def _materialize(candidate: _Candidate, source_snapshot: str) -> EvidenceWindow:
    focus = candidate.focus
    window_id = sha256_text(f"{source_snapshot}:window:{focus.event_id}")
    messages = tuple(_study_message(item) for item in candidate.context)
    payload = {
        "window_id": window_id,
        "source_dependencies": tuple(
            sorted({item.source_id for item in (*candidate.context, candidate.focus)})
        ),
        "conversation_id": focus.conversation_id,
        "parent_thread_id": focus.metadata.get("thread_parent_key"),
        "turn_id": focus.metadata.get("turn_key"),
        "dependency_component_id": candidate.component_id,
        "lineage_completeness": "partial" if focus.metadata.get("thread_parent_key") else "unknown",
        "selection_arm": "challenge" if candidate.tags else "sampled",
        "challenge_tags": candidate.tags,
        "context": messages,
        "focus": _study_message(focus),
        "source_data_class": focus.data_class,
    }
    draft = cast(Any, EvidenceWindow).model_construct(**payload, window_sha256="0" * 64)
    receipt = canonical_sha256(draft.model_dump(mode="json", exclude={"window_sha256"}))
    return EvidenceWindow.model_validate({**payload, "window_sha256": receipt})


def _study_message(event: SourceEvent) -> StudyMessage:
    return StudyMessage(
        event_id=event.event_id,
        speaker=event.speaker,
        structural_claim_holder=event.claim_holder,
        source_authority=event.source_authority,
        content=event.content,
        content_sha256=event.content_sha256,
        event_time=event.event_time,
        sequence_index=int(event.metadata["sequence_index"]),
    )


def _sequence_key(event: SourceEvent) -> tuple[int, str]:
    return int(event.metadata.get("sequence_index", 0)), event.event_id


def _stable_key(candidate: _Candidate, namespace: str) -> str:
    return sha256_text(f"{namespace}:{candidate.focus.event_id}")


def _temporal_key(candidate: _Candidate, namespace: str) -> tuple[datetime, str]:
    assert candidate.focus.event_time is not None
    return candidate.focus.event_time, _stable_key(candidate, namespace)
