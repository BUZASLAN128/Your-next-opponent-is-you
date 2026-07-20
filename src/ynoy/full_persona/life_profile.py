from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from ynoy.errors import DataValidationError
from ynoy.full_persona.identity_rules import (
    LIFE_TOPIC_ORDER,
    LifeTopic,
    is_imported_identity_text,
    life_facts,
)
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.base import DataClass
from ynoy.models.full_persona import (
    EvidenceRole,
    FullCorpusEvidence,
    FullCorpusHead,
    FullCorpusManifest,
)
from ynoy.models.persona_life_profile import (
    PersonaLifeCandidate,
    PersonaLifeProfile,
    PersonaLifeSupport,
    PersonaLifeTopic,
)
from ynoy.util import canonical_sha256

_MAX_CANDIDATES_PER_TOPIC = 8
_MAX_UNIQUE_MATCHES = 4_096
_MAX_SUPPORT_RELATIONS = 65_536
_MAX_SUPPORTS_PER_CANDIDATE = 64
_MAX_CLAIM_CHARS = 512
_WINDOW_STRIDE = 400
_SENTENCE_SPLIT = re.compile(r"(?:\r?\n)+|(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class _SupportState:
    evidence_id: str
    evidence_sha256: str
    source_receipt: str
    observed_at: datetime


@dataclass(slots=True)
class _CandidateState:
    topic: LifeTopic
    semantic_sha256: str
    claim: str
    supports: dict[str, _SupportState]
    first_observed_at: datetime
    last_observed_at: datetime

    @property
    def observation_count(self) -> int:
        return len(self.supports)

    def observe(self, item: FullCorpusEvidence) -> bool:
        if item.evidence_id in self.supports:
            return False
        self.supports[item.evidence_id] = _support_state(item)
        self.first_observed_at = min(self.first_observed_at, item.event_time)
        self.last_observed_at = max(self.last_observed_at, item.event_time)
        return True


@dataclass(slots=True)
class _LifeAccumulator:
    values: dict[LifeTopic, dict[str, _CandidateState]] = field(
        default_factory=lambda: {topic: {} for topic in LIFE_TOPIC_ORDER}
    )
    matched_evidence: dict[LifeTopic, int] = field(
        default_factory=lambda: {topic: 0 for topic in LIFE_TOPIC_ORDER}
    )
    scanned_evidence_count: int = 0
    support_relation_count: int = 0

    def observe(self, item: FullCorpusEvidence) -> None:
        self.scanned_evidence_count += 1
        if item.role != EvidenceRole.DIRECT or is_imported_identity_text(item.content):
            return
        matched: set[LifeTopic] = set()
        for claim in _claim_windows(item.content):
            for topic, fact in life_facts(claim):
                self._observe_claim(topic, fact, item)
                matched.add(topic)
        for topic in matched:
            self.matched_evidence[topic] += 1

    def _observe_claim(self, topic: LifeTopic, claim: str, item: FullCorpusEvidence) -> None:
        normalized = " ".join(claim.casefold().split())
        semantic = canonical_sha256({"topic": topic, "claim": normalized})
        current = self.values[topic].get(semantic)
        if current is not None:
            if current.observe(item):
                self._reserve_support()
            return
        if sum(len(values) for values in self.values.values()) >= _MAX_UNIQUE_MATCHES:
            raise DataValidationError(
                "life_profile_match_limit", "Life-profile matches exceeded their bounded limit."
            )
        self._reserve_support()
        self.values[topic][semantic] = _state(topic, semantic, claim, item)

    def _reserve_support(self) -> None:
        self.support_relation_count += 1
        if self.support_relation_count > _MAX_SUPPORT_RELATIONS:
            raise DataValidationError(
                "life_profile_support_limit",
                "Life-profile provenance exceeded its bounded support limit.",
            )


def build_verified_life_profile(
    store: FullPersonaStore,
    manifest: FullCorpusManifest,
    head: FullCorpusHead,
) -> PersonaLifeProfile:
    if head.status != "complete" or manifest.run_id != head.run_id:
        raise DataValidationError(
            "life_profile_source_incomplete", "Life profile requires a complete source run."
        )
    verify_committed_run(store, manifest, head)
    accumulator = _LifeAccumulator()
    for item in iter_verified_evidence(store, manifest, head):
        accumulator.observe(item)
    if accumulator.scanned_evidence_count != head.evidence_count:
        raise DataValidationError(
            "life_profile_evidence_mismatch", "Life profile did not consume all source evidence."
        )
    topics = tuple(_topic(accumulator, key) for key in LIFE_TOPIC_ORDER)
    return _seal_profile(manifest, head, accumulator.scanned_evidence_count, topics)


def _claim_windows(content: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw in _SENTENCE_SPLIT.split(content):
        sentence = raw.strip(" \t#>*-")
        if not sentence:
            continue
        if len(sentence) <= _MAX_CLAIM_CHARS:
            result.append(sentence)
            continue
        for start in range(0, len(sentence), _WINDOW_STRIDE):
            window = sentence[start : start + _MAX_CLAIM_CHARS].strip()
            if window:
                result.append(window)
            if start + _MAX_CLAIM_CHARS >= len(sentence):
                break
    return tuple(result)


def _state(
    topic: LifeTopic, semantic: str, claim: str, item: FullCorpusEvidence
) -> _CandidateState:
    return _CandidateState(
        topic=topic,
        semantic_sha256=semantic,
        claim=claim,
        supports={item.evidence_id: _support_state(item)},
        first_observed_at=item.event_time,
        last_observed_at=item.event_time,
    )


def _topic(accumulator: _LifeAccumulator, key: LifeTopic) -> PersonaLifeTopic:
    ranked = sorted(
        accumulator.values[key].values(),
        key=lambda item: (
            -item.last_observed_at.timestamp(),
            -item.observation_count,
            item.semantic_sha256,
        ),
    )
    candidates = tuple(_candidate(item) for item in ranked[:_MAX_CANDIDATES_PER_TOPIC])
    return PersonaLifeTopic(
        key=key,
        evidence_state="literal_candidates" if candidates else "unknown",
        matched_evidence_count=accumulator.matched_evidence[key],
        unique_candidate_count=len(accumulator.values[key]),
        candidates=candidates,
        unknowns=_unknowns(key, bool(candidates)),
    )


def _candidate(item: _CandidateState) -> PersonaLifeCandidate:
    states = tuple(sorted(item.supports.values(), key=lambda value: value.evidence_id))
    supports = tuple(_support(value) for value in states[:_MAX_SUPPORTS_PER_CANDIDATE])
    return PersonaLifeCandidate(
        topic=item.topic,
        semantic_sha256=item.semantic_sha256,
        claim=item.claim,
        supports=supports,
        support_count=item.observation_count,
        support_projection_exhaustive=len(supports) == item.observation_count,
        first_observed_at=item.first_observed_at,
        last_observed_at=item.last_observed_at,
        observation_count=item.observation_count,
    )


def _support_state(item: FullCorpusEvidence) -> _SupportState:
    return _SupportState(
        evidence_id=item.evidence_id,
        evidence_sha256=item.evidence_sha256,
        source_receipt=item.source_receipt,
        observed_at=item.event_time,
    )


def _support(item: _SupportState) -> PersonaLifeSupport:
    payload = {
        "evidence_id": item.evidence_id,
        "evidence_sha256": item.evidence_sha256,
        "source_receipt": item.source_receipt,
        "observed_at": item.observed_at,
    }
    draft = cast(Any, PersonaLifeSupport).model_construct(**payload, support_sha256="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"support_sha256"})
    return PersonaLifeSupport.model_validate(
        {**normalized, "support_sha256": canonical_sha256(normalized)}
    )


def _unknowns(key: LifeTopic, has_candidates: bool) -> tuple[str, ...]:
    if has_candidates:
        return ("current_meaning_and_adoption_unreviewed",)
    return (f"{key}_not_established_by_literal_direct_evidence",)


def _seal_profile(
    manifest: FullCorpusManifest,
    head: FullCorpusHead,
    scanned: int,
    topics: tuple[PersonaLifeTopic, ...],
) -> PersonaLifeProfile:
    profile_id = canonical_sha256(
        {
            "source_head_sha256": head.head_sha256,
            "topics": [item.model_dump(mode="json") for item in topics],
        }
    )
    payload: dict[str, object] = {
        "profile_id": profile_id,
        "source_run_id": manifest.run_id,
        "source_manifest_sha256": manifest.manifest_sha256,
        "source_head_sha256": head.head_sha256,
        "source_head_revision": head.revision,
        "expires_at": manifest.expires_at,
        "data_class": (
            DataClass.PUBLIC_SYNTHETIC if manifest.synthetic else DataClass.DERIVED_IDENTITY
        ),
        "synthetic": manifest.synthetic,
        "scanned_evidence_count": scanned,
        "topics": topics,
    }
    draft = cast(Any, PersonaLifeProfile).model_construct(**payload, profile_sha256="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"profile_sha256"})
    return PersonaLifeProfile.model_validate(
        {**normalized, "profile_sha256": canonical_sha256(normalized)}
    )
