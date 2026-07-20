from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from support.persona_pack import built_pack

from ynoy.full_persona.persona_adjudication import (
    adjudication_action_counts,
    build_persona_adjudication,
)
from ynoy.full_persona.persona_evolution import build_persona_evolution
from ynoy.models.persona_adjudication import (
    PersonaAdjudicationProfile,
    SystemPersonaRecommendation,
)
from ynoy.models.persona_evolution import PersonaEvolutionProfile
from ynoy.util import canonical_sha256


def test_adjudication_is_deterministic_and_receipt_bound(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    evolution = build_persona_evolution(pack)

    first = build_persona_adjudication(evolution)
    second = build_persona_adjudication(evolution)

    assert first == second
    assert first.pack_id == evolution.pack_id == pack.pack_id
    assert first.pack_sha256 == evolution.pack_sha256 == pack.pack_sha256
    assert first.evolution_sha256 == evolution.evolution_sha256
    assert first.source_pattern_candidate_count == evolution.total_pattern_candidate_count
    assert first.source_transition_candidate_count == evolution.total_transition_candidate_count
    assert first.omitted_candidate_count == 0
    assert first.review_projection_status == "complete"
    assert first.review_projection_exhaustive is True
    assert first.represented_user_review == "not_performed"
    assert first.verified_adoption_available is False
    assert first.persona_quality_claimed is False
    assert first.automatic_core_promotion is False
    assert first.authority == "none"


def test_recommendations_are_non_adopting_and_use_only_allowed_actions(
    tmp_path: Path,
) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_adjudication(build_persona_evolution(pack))
    allowed_actions = {
        "simulate_as_hypothesis",
        "prioritize_for_review",
        "defer_more_evidence",
        "defer_scope_required",
    }
    allowed_uses = {"shadow_simulation_only", "review_prioritization_only"}

    assert {item.action for item in profile.recommendations} <= allowed_actions
    assert {item.use for item in profile.recommendations} <= allowed_uses
    for item in profile.recommendations:
        assert item.user_adoption == "not_provided"
        assert item.currentness_status == "not_established"
        assert item.semantic_adoption == "not_established"
        assert item.adopted is False
        assert item.core_eligible is False
        assert item.authority == "none"
        if item.action == "simulate_as_hypothesis":
            assert item.use == "shadow_simulation_only"
        else:
            assert item.use == "review_prioritization_only"


@pytest.mark.parametrize(
    ("strength", "evidence_count", "action", "rationale"),
    (
        (
            "high_repetition",
            20,
            "simulate_as_hypothesis",
            "high_repetition_direct_evidence",
        ),
        ("repeated", 5, "prioritize_for_review", "repeated_direct_evidence"),
        ("weak_repetition", 2, "defer_more_evidence", "weak_repetition_only"),
    ),
)
def test_pattern_strength_maps_to_deterministic_review_disposition(
    tmp_path: Path,
    strength: str,
    evidence_count: int,
    action: str,
    rationale: str,
) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    evolution = build_persona_evolution(pack)
    adjusted = _evolution_with_pattern_strength(evolution, strength, evidence_count)

    profile = build_persona_adjudication(adjusted)
    pattern = next(item for item in profile.recommendations if item.target_kind == "pattern")

    assert pattern.action == action
    assert pattern.rationale == rationale
    assert pattern.evidence_count == evidence_count
    assert pattern.scope_status == "not_established"


def test_transitions_are_always_scope_deferred(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_adjudication(build_persona_evolution(pack))
    transitions = [item for item in profile.recommendations if item.target_kind == "transition"]

    assert transitions
    assert all(item.action == "defer_scope_required" for item in transitions)
    assert all(item.rationale == "contextual_transition_scope_unknown" for item in transitions)
    assert all(item.scope_status == "not_established" for item in transitions)
    assert all(item.use == "review_prioritization_only" for item in transitions)


def test_profile_hash_tampering_fails_closed(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_adjudication(build_persona_evolution(pack))
    payload = profile.model_dump(mode="json")
    payload["adjudication_sha256"] = "0" * 64

    with pytest.raises(ValidationError, match="persona adjudication hash does not match"):
        PersonaAdjudicationProfile.model_validate(payload)


def test_action_and_rationale_mismatch_fails_closed(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_adjudication(build_persona_evolution(pack))
    payload = profile.recommendations[0].model_dump(mode="json")
    payload["rationale"] = "weak_repetition_only"
    identity_fields = (
        "target_kind",
        "target_id",
        "action",
        "rationale",
        "evidence_count",
        "scope_status",
        "currentness_status",
        "use",
        "system_actor",
    )
    payload["recommendation_id"] = canonical_sha256({key: payload[key] for key in identity_fields})

    with pytest.raises(ValidationError, match="contradicts its rationale"):
        SystemPersonaRecommendation.model_validate(payload)


def test_source_binding_mismatch_fails_closed_in_full_package(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    from ynoy.full_persona.persona_package import build_full_persona_package
    from ynoy.models.persona_package import FullPersonaPackage

    package = build_full_persona_package(pack)
    payload = package.model_dump(mode="json")
    payload["adjudication"]["pack_sha256"] = "0" * 64
    payload["adjudication"]["adjudication_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in payload["adjudication"].items()
            if key != "adjudication_sha256"
        }
    )
    payload["package_id"] = canonical_sha256(
        {
            "protocol_version": payload["protocol_version"],
            "pack_sha256": payload["pack_sha256"],
            "dossier_sha256": payload["dossier"]["dossier_sha256"],
            "evolution_sha256": payload["evolution"]["evolution_sha256"],
            "adjudication_sha256": payload["adjudication"]["adjudication_sha256"],
        }
    )
    payload["package_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "package_sha256"}
    )

    with pytest.raises(ValidationError, match="persona package projections"):
        FullPersonaPackage.model_validate(payload)


def test_duplicate_target_ids_are_rejected(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_adjudication(build_persona_evolution(pack))
    assert len(profile.recommendations) >= 2
    payload = profile.model_dump(mode="json")
    payload["recommendations"][1] = dict(payload["recommendations"][0])
    payload["adjudication_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "adjudication_sha256"}
    )

    with pytest.raises(ValidationError, match="target-unique"):
        PersonaAdjudicationProfile.model_validate(payload)


def test_action_counts_are_stable_and_content_free(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    profile = build_persona_adjudication(build_persona_evolution(pack))

    counts = adjudication_action_counts(profile)

    assert sum(counts.values()) == len(profile.recommendations)
    assert tuple(counts) == tuple(sorted(counts))
    assert all(isinstance(value, int) and value >= 0 for value in counts.values())
    rendered = repr(counts)
    assert "Doğum" not in rendered
    assert "PRIVATE_CONTEXT_" not in rendered


def test_adjudication_reports_bounded_evolution_overflow(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    evolution = build_persona_evolution(pack)
    payload = evolution.model_dump(mode="json")
    payload["total_transition_candidate_count"] += 3
    payload["evolution_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "evolution_sha256"}
    )
    bounded = PersonaEvolutionProfile.model_validate(payload)

    profile = build_persona_adjudication(bounded)

    assert profile.review_projection_status == "bounded_partial"
    assert profile.review_projection_exhaustive is False
    assert profile.omitted_candidate_count == 3


def _evolution_with_pattern_strength(
    evolution: PersonaEvolutionProfile, strength: str, evidence_count: int
) -> PersonaEvolutionProfile:
    payload = evolution.model_dump(mode="json")
    pattern = dict(payload["patterns"][0])
    pattern["evidence_strength"] = strength
    pattern["evidence_count"] = evidence_count
    pattern["distinct_atom_count"] = min(pattern["distinct_atom_count"], evidence_count)
    pattern["evidence_refs"] = pattern["evidence_refs"][: pattern["distinct_atom_count"]]
    payload["patterns"] = [pattern]
    payload["evolution_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "evolution_sha256"}
    )
    return PersonaEvolutionProfile.model_validate(payload)
