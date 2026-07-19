from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ynoy.errors import DataValidationError
from ynoy.full_persona.pack_rules import (
    claim_for,
    primary_layer,
    ranking_score,
    semantic_key,
)
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.recovery import recover_interrupted_run
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.base import DataClass
from ynoy.models.full_persona import FullCorpusEvidence, FullCorpusHead, FullCorpusManifest
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaAtomStatus,
    PersonaEvidenceBasis,
    PersonaLayer,
    PersonaLayerView,
    PersonaPack,
    PersonaPackBuildConfig,
    PersonaSupportRef,
)
from ynoy.util import canonical_sha256, sha256_text, utc_now

_PACK_UNKNOWNS = (
    "birth_history_not_established_without_literal_evidence",
    "observed_utterance_does_not_establish_current_adoption",
    "persona_similarity_not_calibrated",
    "relationship_truth_not_established",
    "demonstrated_skill_not_established",
)
_LAYER_UNKNOWNS: dict[PersonaLayer, tuple[str, ...]] = {
    PersonaLayer.TIMELINE: ("life_timeline_outside_observed_conversations_unknown",),
    PersonaLayer.AUTOBIOGRAPHY: ("biography_requires_literal_user_evidence",),
    PersonaLayer.VALUES: ("stable_values_not_adopted",),
    PersonaLayer.GOALS: ("current_goal_status_unknown",),
    PersonaLayer.DECISIONS: ("decision_scope_and_current_validity_unreviewed",),
    PersonaLayer.EVIDENCE: ("semantic_meaning_not_adopted",),
    PersonaLayer.RISK: ("risk_tolerance_not_calibrated",),
    PersonaLayer.KNOWLEDGE: ("knowledge_depth_not_demonstrated",),
    PersonaLayer.SKILLS: ("skill_performance_not_demonstrated",),
    PersonaLayer.RELATIONSHIPS: ("relationship_claims_not_adopted",),
    PersonaLayer.CONTRADICTIONS: ("conflicts_remain_unresolved",),
    PersonaLayer.RESPONSE_POLICY: ("response_preferences_not_calibrated",),
}


@dataclass(slots=True)
class _RankedAtom:
    rank: tuple[int, str]
    atom: PersonaAtom


@dataclass(slots=True)
class _PackAccumulator:
    config: PersonaPackBuildConfig
    values: dict[PersonaLayer, list[_RankedAtom]] = field(
        default_factory=lambda: {layer: [] for layer in PersonaLayer}
    )
    processed: int = 0

    def observe(self, evidence: FullCorpusEvidence) -> None:
        self.processed += 1
        excerpt = evidence.content[: self.config.max_excerpt_chars]
        support = _support(evidence, excerpt)
        self._retain(
            _atom(evidence, PersonaLayer.TIMELINE, PersonaAtomStatus.OBSERVED, support),
            ranking_score(evidence, PersonaLayer.TIMELINE),
        )
        layer, status = primary_layer(evidence)
        self._retain(_atom(evidence, layer, status, support), ranking_score(evidence, layer))

    def _retain(self, atom: PersonaAtom, score: int) -> None:
        ranked = self.values[atom.layer]
        candidate = _RankedAtom((score, atom.atom_id), atom)
        if any(item.atom.atom_id == atom.atom_id for item in ranked):
            return
        if len(ranked) < self.config.max_atoms_per_layer:
            ranked.append(candidate)
            return
        lowest = min(range(len(ranked)), key=lambda index: ranked[index].rank)
        if candidate.rank > ranked[lowest].rank:
            ranked[lowest] = candidate

    def layers(self) -> tuple[PersonaLayerView, ...]:
        return tuple(
            PersonaLayerView(
                layer=layer,
                atoms=tuple(sorted((item.atom for item in self.values[layer]), key=_atom_id)),
                unknowns=_LAYER_UNKNOWNS[layer],
            )
            for layer in PersonaLayer
        )


def build_deterministic_pack(
    private_root: Path,
    run_id: str,
    *,
    synthetic: bool,
    config: PersonaPackBuildConfig | None = None,
) -> PersonaPack:
    """Build a bounded proposal pack from every verified evidence record."""
    selected = config or PersonaPackBuildConfig()
    manifest, head, accumulator = _accumulate(
        private_root, run_id, synthetic=synthetic, config=selected
    )
    layers = accumulator.layers()
    pack_id = canonical_sha256(
        {
            "source_run_id": run_id,
            "source_head_sha256": head.head_sha256,
            "config_sha256": selected.config_sha256,
        }
    )
    payload = {
        "pack_id": pack_id,
        "source_run_id": run_id,
        "source_manifest_sha256": manifest.manifest_sha256,
        "source_head_sha256": head.head_sha256,
        "source_head_revision": head.revision,
        "expires_at": manifest.expires_at,
        "config": selected,
        "data_class": DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY,
        "synthetic": synthetic,
        "processed_evidence_count": accumulator.processed,
        "retained_atom_count": sum(len(layer.atoms) for layer in layers),
        "layers": layers,
        "unknowns": _PACK_UNKNOWNS,
    }
    draft = cast(Any, PersonaPack).model_construct(**payload, pack_sha256="0" * 64)
    return PersonaPack.model_validate(
        {
            **payload,
            "pack_sha256": canonical_sha256(draft.model_dump(mode="json", exclude={"pack_sha256"})),
        }
    )


def _accumulate(
    private_root: Path,
    run_id: str,
    *,
    synthetic: bool,
    config: PersonaPackBuildConfig,
) -> tuple[FullCorpusManifest, FullCorpusHead, _PackAccumulator]:
    store = FullPersonaStore(private_root, synthetic=synthetic)
    with store.lock(run_id):
        manifest = store.read_manifest(run_id)
        if manifest.expires_at <= utc_now():
            raise DataValidationError(
                "persona_pack_source_expired", "An expired corpus cannot produce a persona pack."
            )
        head = recover_interrupted_run(store, manifest, store.read_head(run_id))
        if head.status != "complete":
            raise DataValidationError(
                "persona_pack_source_not_complete",
                "A deterministic persona pack requires a completed corpus scan.",
            )
        accumulator = _PackAccumulator(config)
        for evidence in iter_verified_evidence(store, manifest, head):
            accumulator.observe(evidence)
    if accumulator.processed != head.evidence_count:
        raise DataValidationError(
            "persona_pack_evidence_count_mismatch",
            "Persona pack evidence did not reconcile to the source head.",
        )
    return manifest, head, accumulator


def _support(evidence: FullCorpusEvidence, excerpt: str) -> PersonaSupportRef:
    payload = {
        "evidence_id": evidence.evidence_id,
        "evidence_sha256": evidence.evidence_sha256,
        "source_key": evidence.source_key,
        "content_sha256": evidence.content_sha256,
        "byte_start": evidence.byte_start,
        "byte_length": evidence.byte_length,
        "line_number": evidence.line_number,
        "event_time": evidence.event_time,
        "time_basis": evidence.time_basis,
        "evidence_role": evidence.role,
        "char_start": 0,
        "char_end": len(excerpt),
        "excerpt": excerpt,
        "excerpt_sha256": sha256_text(excerpt),
    }
    draft = cast(Any, PersonaSupportRef).model_construct(**payload, support_sha256="0" * 64)
    return PersonaSupportRef.model_validate(
        {
            **payload,
            "support_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"support_sha256"})
            ),
        }
    )


def _atom(
    evidence: FullCorpusEvidence,
    layer: PersonaLayer,
    status: PersonaAtomStatus,
    support: PersonaSupportRef,
) -> PersonaAtom:
    claim = claim_for(evidence, layer, support.excerpt)
    payload = {
        "layer": layer,
        "semantic_key": semantic_key(layer, claim),
        "claim": claim,
        "basis": PersonaEvidenceBasis.LITERAL,
        "status": status,
        "source_role": evidence.role,
        "support": (support,),
        "evidence_ids": (support.evidence_id,),
        "evidence_receipts": (support.support_sha256,),
        "observation_count": 1,
        "first_observed_at": evidence.event_time,
        "last_observed_at": evidence.event_time,
    }
    draft = cast(Any, PersonaAtom).model_construct(**payload, atom_id="0" * 64)
    return PersonaAtom.model_validate(
        {
            **payload,
            "atom_id": canonical_sha256(draft.model_dump(mode="json", exclude={"atom_id"})),
        }
    )


def _atom_id(atom: PersonaAtom) -> str:
    return atom.atom_id
