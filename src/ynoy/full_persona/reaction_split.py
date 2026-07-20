from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Never

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.reaction_contracts import (
    CompactReactionEvent,
    build_case,
    build_history,
    build_manifest,
    build_target_seal,
)
from ynoy.full_persona.reaction_evidence import compact_reaction_events
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import (
    FullCorpusEvidence,
    FullCorpusHead,
    FullCorpusManifest,
)
from ynoy.models.persona_reaction_benchmark import (
    PersonaReactionCase,
    PersonaReactionHistory,
    PersonaReactionManifest,
    PersonaReactionTargetSeal,
)
from ynoy.util import canonical_sha256

_MAX_HISTORY_EVENTS = 8_192
_MAX_CASES_PER_COMPONENT = 3
_MIN_HISTORY_EVENTS = 8
_MIN_SEALED_CLUSTERS = 8


@dataclass(frozen=True, slots=True)
class ReactionSplit:
    manifest: PersonaReactionManifest
    history: tuple[PersonaReactionHistory, ...]
    cases: tuple[PersonaReactionCase, ...]
    target_seal: PersonaReactionTargetSeal

    def __post_init__(self) -> None:
        if tuple(item.history_id for item in self.history) != (
            self.manifest.development_history_ids
        ):
            _split_error("reaction history does not match its manifest")
        if tuple(item.case_id for item in self.cases) != self.manifest.sealed_case_ids:
            _split_error("reaction cases do not match their manifest")
        validate_reaction_target_seal(self.manifest, self.target_seal)

    @property
    def sealed_cases(self) -> tuple[PersonaReactionCase, ...]:
        return self.cases


def build_reaction_split(
    source_manifest: FullCorpusManifest,
    evidence: Iterable[FullCorpusEvidence],
    *,
    sealed_count: int = 24,
) -> ReactionSplit:
    """Build a D0 synthetic split; real data must use the verified-store entrypoint."""
    if not source_manifest.synthetic:
        _split_error("real reaction evidence requires a verified full-corpus store")
    return _build_reaction_split(
        source_manifest,
        evidence,
        sealed_count=sealed_count,
        source_head_sha256=source_manifest.manifest_sha256,
        source_head_revision=0,
        evidence_authentication="synthetic_fixture",
    )


def build_verified_reaction_split(
    store: FullPersonaStore,
    source_manifest: FullCorpusManifest,
    source_head: FullCorpusHead,
    *,
    sealed_count: int = 24,
) -> ReactionSplit:
    """Build a private split only after the complete shard and receipt chain verifies."""
    if source_manifest.synthetic or source_head.status != "complete":
        _split_error("verified reaction split requires a complete private source run")
    if (
        source_head.run_id != source_manifest.run_id
        or source_head.manifest_sha256 != source_manifest.manifest_sha256
    ):
        _split_error("reaction source head does not match its manifest")
    verify_committed_run(store, source_manifest, source_head)
    return _build_reaction_split(
        source_manifest,
        iter_verified_evidence(store, source_manifest, source_head),
        sealed_count=sealed_count,
        source_head_sha256=source_head.head_sha256,
        source_head_revision=source_head.revision,
        evidence_authentication="verified_full_corpus_store",
    )


def _build_reaction_split(
    source_manifest: FullCorpusManifest,
    evidence: Iterable[FullCorpusEvidence],
    *,
    sealed_count: int,
    source_head_sha256: str,
    source_head_revision: int,
    evidence_authentication: str,
) -> ReactionSplit:
    if not isinstance(evidence, Iterable) or sealed_count != 24:
        _split_error("reaction benchmark requires exactly 24 iterable sealed candidates")
    manifest = _validated_manifest(source_manifest)
    sources = {item.source_key: item for item in manifest.files}
    events = compact_reaction_events(evidence, sources, manifest)
    sealed = _select_sealed(events, sealed_count)
    history = _select_history(events, sealed)
    cutoff = _temporal_cutoff(history, sealed)
    history_models = tuple(
        build_history(item, data_class=manifest.source_data_class, synthetic=manifest.synthetic)
        for item in history
    )
    case_models = tuple(
        build_case(
            manifest.run_id,
            item,
            data_class=manifest.source_data_class,
            synthetic=manifest.synthetic,
        )
        for item in sealed
    )
    reaction_manifest = build_manifest(
        manifest,
        history_models,
        case_models,
        cutoff,
        source_head_sha256=source_head_sha256,
        source_head_revision=source_head_revision,
        evidence_authentication=evidence_authentication,
    )
    target_seal = build_target_seal(reaction_manifest, sealed, case_models)
    return ReactionSplit(reaction_manifest, history_models, case_models, target_seal)


def _validated_manifest(value: FullCorpusManifest) -> FullCorpusManifest:
    try:
        return FullCorpusManifest.model_validate(value.model_dump(mode="json"))
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_source_manifest_invalid", "Reaction source manifest is invalid."
        ) from exc


def _select_sealed(
    events: tuple[CompactReactionEvent, ...], sealed_count: int
) -> tuple[CompactReactionEvent, ...]:
    selected: list[CompactReactionEvent] = []
    source_counts: Counter[str] = Counter()
    conversation_counts: Counter[str] = Counter()
    component_counts: Counter[str] = Counter()
    content_hashes: set[str] = set()
    ordered = sorted(events, key=lambda item: (item.event_time, item.evidence_id), reverse=True)
    for item in ordered:
        if item.content_sha256 in content_hashes or any(
            counts[key] >= _MAX_CASES_PER_COMPONENT
            for counts, key in (
                (source_counts, item.source_key),
                (conversation_counts, item.conversation_key),
                (component_counts, item.lineage_component_receipt),
            )
        ):
            continue
        selected.append(item)
        content_hashes.add(item.content_sha256)
        source_counts[item.source_key] += 1
        conversation_counts[item.conversation_key] += 1
        component_counts[item.lineage_component_receipt] += 1
        if len(selected) == sealed_count:
            break
    clusters = {item.lineage_component_receipt for item in selected}
    if len(selected) != sealed_count or len(clusters) < _MIN_SEALED_CLUSTERS:
        _split_error("reaction evidence cannot form 24 cases across eight sealed clusters")
    return tuple(sorted(selected, key=lambda item: (item.event_time, item.evidence_id)))


def _select_history(
    events: tuple[CompactReactionEvent, ...], sealed: tuple[CompactReactionEvent, ...]
) -> tuple[CompactReactionEvent, ...]:
    earliest = min(item.event_time for item in sealed)
    sealed_sources = {item.source_key for item in sealed}
    sealed_receipts = {item.source_receipt for item in sealed}
    sealed_conversations = {item.conversation_key for item in sealed}
    sealed_components = {item.lineage_component_receipt for item in sealed}
    sealed_content = {item.content_sha256 for item in sealed}
    selected = tuple(
        item
        for item in events
        if item.event_time < earliest
        and item.source_key not in sealed_sources
        and item.source_receipt not in sealed_receipts
        and item.conversation_key not in sealed_conversations
        and item.lineage_component_receipt not in sealed_components
        and item.content_sha256 not in sealed_content
    )
    selected = tuple(sorted(selected, key=lambda item: (item.event_time, item.evidence_id)))
    if not _MIN_HISTORY_EVENTS <= len(selected) <= _MAX_HISTORY_EVENTS:
        _split_error("reaction development history is outside its bounded support range")
    if len({item.signal for item in selected}) < 2:
        _split_error("reaction development history needs at least two observed signal classes")
    return selected


def _temporal_cutoff(
    history: tuple[CompactReactionEvent, ...], sealed: tuple[CompactReactionEvent, ...]
) -> datetime:
    latest_history = max(item.event_time for item in history)
    earliest_sealed = min(item.event_time for item in sealed)
    if latest_history >= earliest_sealed:
        _split_error("reaction development and sealed time ranges overlap")
    return latest_history + (earliest_sealed - latest_history) / 2


def _split_error(reason: str) -> Never:
    raise DataValidationError("reaction_split_invalid", reason)


def validate_reaction_target_seal(
    manifest: PersonaReactionManifest, seal: PersonaReactionTargetSeal
) -> None:
    locator_ids = tuple(item.case_id for item in seal.locators)
    derived_ids = tuple(
        canonical_sha256({"run_id": manifest.source_run_id, "evidence_id": item.evidence_id})
        for item in seal.locators
    )
    if (
        seal.manifest_sha256 != manifest.manifest_sha256
        or locator_ids != manifest.sealed_case_ids
        or locator_ids != derived_ids
    ):
        _split_error("reaction target seal does not match its target-free manifest")
