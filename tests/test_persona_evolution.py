from __future__ import annotations

import pytest
from pydantic import ValidationError
from support.persona_pack import built_pack, pack_atoms

from ynoy.full_persona.persona_evolution import build_persona_evolution
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import PersonaLayer
from ynoy.models.persona_evolution import PersonaEvolutionProfile


def test_evolution_profile_is_deterministic_and_unadopted(tmp_path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)

    first = build_persona_evolution(pack)
    second = build_persona_evolution(pack)

    assert first == second
    assert first.pack_id == pack.pack_id
    assert first.pack_sha256 == pack.pack_sha256
    assert first.total_pattern_candidate_count == len(first.patterns)
    assert first.total_transition_candidate_count == len(first.transitions)
    assert first.persona_quality_claimed is False
    assert first.automatic_core_promotion is False
    assert first.authority == "none"
    assert all(item.status == "derived_unadopted" for item in first.patterns)
    assert all(item.use == "proposal_context_only" for item in first.patterns)
    assert all(item.adopted is False for item in first.patterns)


def test_synthetic_chronology_produces_contextual_planning_transition(tmp_path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)

    profile = build_persona_evolution(pack)
    planning = [item for item in profile.transitions if item.dimension == "planning_mode"]

    assert [(item.from_state, item.to_state) for item in planning] == [
        ("plan_first", "execute_now")
    ]
    transition = planning[0]
    assert transition.status == "contextual_transition_candidate"
    assert transition.scope_status == "not_established"
    assert transition.semantic_adoption == "not_established"
    assert transition.adopted is False
    assert transition.core_eligible is False
    assert transition.authority == "none"


def test_evolution_uses_only_direct_evidence_and_no_probability(tmp_path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)

    profile = build_persona_evolution(pack)
    atoms = {atom.atom_id: atom for atom in pack_atoms(pack)}
    refs = [ref for item in profile.patterns for ref in item.evidence_refs]
    refs += [item.from_evidence for item in profile.transitions]
    refs += [item.to_evidence for item in profile.transitions]

    assert refs
    assert all(atoms[ref.atom_id].source_role == EvidenceRole.DIRECT for ref in refs)
    assert all(atoms[ref.atom_id].layer != PersonaLayer.TIMELINE for ref in refs)
    assert "confidence" not in profile.model_dump(mode="json")
    assert "calibrated_probability" not in profile.model_dump(mode="json")
    assert "candidate_scope_not_established" in profile.unknowns


def test_evolution_hash_tampering_fails_closed(tmp_path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_evolution(pack)
    payload = profile.model_dump(mode="json")
    payload["evolution_sha256"] = "0" * 64

    with pytest.raises(ValidationError, match="persona evolution hash does not match"):
        PersonaEvolutionProfile.model_validate(payload)
