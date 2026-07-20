# ruff: noqa: RUF001 -- Turkish pattern matching is intentional.

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any, cast

from ynoy.full_persona.identity_rules import is_imported_identity_text
from ynoy.full_persona.response_context import STYLE_RULES
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaAtomStatus,
    PersonaLayer,
    PersonaPack,
)
from ynoy.models.persona_evolution import (
    EvidenceStrength,
    EvolutionDimension,
    EvolutionEvidenceRef,
    EvolutionState,
    PersonaEvolutionProfile,
    PersonaPatternCandidate,
    PersonaTransitionCandidate,
)
from ynoy.util import canonical_sha256

_MAX_PATTERNS = 64
_MAX_TRANSITIONS = 64
_MAX_REFS = 8
_TRANSITION_RULES: tuple[
    tuple[EvolutionDimension, tuple[tuple[EvolutionState, re.Pattern[str]], ...]], ...
] = (
    (
        "planning_mode",
        (
            ("plan_first", re.compile(r"plan yap|planla|önce plan", re.I)),
            ("execute_now", re.compile(r"plansız|direkt yap|işe koyul", re.I)),
        ),
    ),
    (
        "workflow_control",
        (
            (
                "autonomous_momentum",
                re.compile(r"sana bırakıyorum|devam et|kararları sen|bitirene kadar", re.I),
            ),
            ("user_gate", re.compile(r"\bdur\b|\bbekle\b|onay almadan|bana sor", re.I)),
        ),
    ),
    (
        "resource_strategy",
        (
            ("bounded_resources", re.compile(r"düşük ram|ram.*kıs|çökertme|bellek.*sınır", re.I)),
            (
                "exhaustive_processing",
                re.compile(r"hepsini tara|tamamını işle|full.*tara|bütün.*veri", re.I),
            ),
        ),
    ),
)


def build_persona_evolution(pack: PersonaPack) -> PersonaEvolutionProfile:
    """Derive bounded temporal candidates without adopting or authorizing them."""
    atoms = tuple(_direct_atoms(pack))
    all_patterns = _pattern_candidates(atoms)
    all_transitions = _transition_candidates(atoms)
    patterns = all_patterns[:_MAX_PATTERNS]
    transitions = all_transitions[:_MAX_TRANSITIONS]
    unknowns = _unknowns(all_patterns, all_transitions)
    payload: dict[str, object] = {
        "pack_id": pack.pack_id,
        "pack_sha256": pack.pack_sha256,
        "total_pattern_candidate_count": len(all_patterns),
        "total_transition_candidate_count": len(all_transitions),
        "patterns": patterns,
        "transitions": transitions,
        "unknowns": unknowns,
    }
    draft = cast(Any, PersonaEvolutionProfile).model_construct(**payload, evolution_sha256="0" * 64)
    canonical = draft.model_dump(mode="json", exclude={"evolution_sha256"})
    return PersonaEvolutionProfile.model_validate(
        {**canonical, "evolution_sha256": canonical_sha256(canonical)}
    )


def _direct_atoms(pack: PersonaPack) -> Iterable[PersonaAtom]:
    for view in pack.layers:
        for atom in view.atoms:
            if _eligible(atom):
                yield atom


def _eligible(atom: PersonaAtom) -> bool:
    return bool(
        atom.source_role == EvidenceRole.DIRECT
        and atom.layer != PersonaLayer.TIMELINE
        and atom.status
        in {PersonaAtomStatus.OBSERVED, PersonaAtomStatus.PENDING, PersonaAtomStatus.CONFLICTED}
        and atom.evidence_receipts
        and atom.first_observed_at is not None
        and atom.last_observed_at is not None
        and not atom.adopted
        and not is_imported_identity_text(atom.claim)
    )


def _pattern_candidates(atoms: tuple[PersonaAtom, ...]) -> tuple[PersonaPatternCandidate, ...]:
    result: list[PersonaPatternCandidate] = []
    for key, pattern, guidance in STYLE_RULES:
        matches = tuple(atom for atom in atoms if pattern.search(atom.claim))
        evidence_count = sum(atom.observation_count for atom in matches)
        if evidence_count < 2:
            continue
        ordered = sorted(matches, key=_atom_order)
        result.append(
            PersonaPatternCandidate(
                key=key,
                guidance=guidance,
                evidence_count=evidence_count,
                distinct_atom_count=len(matches),
                first_observed_at=_first_observed(ordered[0]),
                last_observed_at=max(_last_observed(atom) for atom in ordered),
                evidence_strength=_strength(evidence_count),
                evidence_refs=tuple(_evidence_ref(atom) for atom in ordered[:_MAX_REFS]),
            )
        )
    return tuple(sorted(result, key=lambda item: item.key))


def _transition_candidates(
    atoms: tuple[PersonaAtom, ...],
) -> tuple[PersonaTransitionCandidate, ...]:
    transitions: list[PersonaTransitionCandidate] = []
    for dimension, states in _TRANSITION_RULES:
        observations = _state_observations(atoms, states)
        previous: tuple[EvolutionState, PersonaAtom] | None = None
        for current in observations:
            if previous is not None and previous[0] != current[0]:
                transitions.append(
                    PersonaTransitionCandidate(
                        dimension=dimension,
                        from_state=previous[0],
                        to_state=current[0],
                        transition_at=_first_observed(current[1]),
                        from_evidence=_evidence_ref(previous[1]),
                        to_evidence=_evidence_ref(current[1]),
                    )
                )
            previous = current
    return tuple(sorted(transitions, key=_transition_order))


def _state_observations(
    atoms: tuple[PersonaAtom, ...],
    states: tuple[tuple[EvolutionState, re.Pattern[str]], ...],
) -> list[tuple[EvolutionState, PersonaAtom]]:
    found: list[tuple[EvolutionState, PersonaAtom]] = []
    for atom in atoms:
        state = next((name for name, pattern in states if pattern.search(atom.claim)), None)
        if state is not None:
            found.append((state, atom))
    found.sort(key=lambda item: _atom_order(item[1]))
    return found


def _evidence_ref(atom: PersonaAtom) -> EvolutionEvidenceRef:
    return EvolutionEvidenceRef(
        atom_id=atom.atom_id,
        evidence_receipt=sorted(set(atom.evidence_receipts))[0],
        observed_at=_first_observed(atom),
    )


def _strength(count: int) -> EvidenceStrength:
    if count >= 20:
        return "high_repetition"
    if count >= 5:
        return "repeated"
    return "weak_repetition"


def _atom_order(atom: PersonaAtom) -> tuple[datetime, str]:
    return _first_observed(atom), atom.atom_id


def _first_observed(atom: PersonaAtom) -> datetime:
    if atom.first_observed_at is None:
        raise ValueError("eligible persona atom lost its first timestamp")
    return atom.first_observed_at


def _last_observed(atom: PersonaAtom) -> datetime:
    if atom.last_observed_at is None:
        raise ValueError("eligible persona atom lost its last timestamp")
    return atom.last_observed_at


def _transition_order(item: PersonaTransitionCandidate) -> tuple[datetime, str, str, str]:
    return item.transition_at, item.dimension, item.from_state, item.to_state


def _unknowns(
    patterns: tuple[PersonaPatternCandidate, ...],
    transitions: tuple[PersonaTransitionCandidate, ...],
) -> tuple[str, ...]:
    result = ["candidate_scope_not_established", "semantic_adoption_not_established"]
    if not patterns:
        result.append("no_repeated_behavior_pattern_established")
    if not transitions:
        result.append("no_contextual_state_transition_established")
    if len(patterns) > _MAX_PATTERNS:
        result.append("pattern_candidate_retention_limit_reached")
    if len(transitions) > _MAX_TRANSITIONS:
        result.append("transition_candidate_retention_limit_reached")
    return tuple(result)
