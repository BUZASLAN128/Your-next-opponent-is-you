from __future__ import annotations

from collections import Counter
from typing import Any, cast

from ynoy.models.persona_adjudication import (
    PersonaAdjudicationProfile,
    RecommendationAction,
    RecommendationRationale,
    RecommendationTargetKind,
    RecommendationUse,
    SystemPersonaRecommendation,
    pattern_recommendation_disposition,
)
from ynoy.models.persona_evolution import (
    PersonaEvolutionProfile,
    PersonaPatternCandidate,
    PersonaTransitionCandidate,
)
from ynoy.util import canonical_sha256


def build_persona_adjudication(
    evolution: PersonaEvolutionProfile,
) -> PersonaAdjudicationProfile:
    """Prioritize evidence candidates without impersonating represented-user adoption."""
    recommendations = tuple(
        sorted(
            (
                *(_pattern_recommendation(item) for item in evolution.patterns),
                *(_transition_recommendation(item) for item in evolution.transitions),
            ),
            key=lambda item: (item.target_kind, item.target_id),
        )
    )
    payload: dict[str, object] = {
        "pack_id": evolution.pack_id,
        "pack_sha256": evolution.pack_sha256,
        "evolution_sha256": evolution.evolution_sha256,
        "source_pattern_candidate_count": evolution.total_pattern_candidate_count,
        "source_transition_candidate_count": evolution.total_transition_candidate_count,
        "omitted_candidate_count": _omitted_count(evolution, recommendations),
        "review_projection_status": _projection_status(evolution, recommendations),
        "review_projection_exhaustive": _omitted_count(evolution, recommendations) == 0,
        "recommendations": recommendations,
    }
    draft = cast(Any, PersonaAdjudicationProfile).model_construct(
        **payload, adjudication_sha256="0" * 64
    )
    canonical = draft.model_dump(mode="json", exclude={"adjudication_sha256"})
    return PersonaAdjudicationProfile.model_validate(
        {**canonical, "adjudication_sha256": canonical_sha256(canonical)}
    )


def adjudication_action_counts(
    profile: PersonaAdjudicationProfile,
) -> dict[str, int]:
    """Return stable aggregate counts without exposing private candidate content."""
    counts = Counter(item.action for item in profile.recommendations)
    return {key: counts[key] for key in sorted(counts)}


def _pattern_recommendation(item: PersonaPatternCandidate) -> SystemPersonaRecommendation:
    action, rationale = pattern_recommendation_disposition(item.evidence_strength)
    return _recommendation(
        target_kind="pattern",
        target_id=_pattern_target_id(item),
        action=action,
        rationale=rationale,
        evidence_count=item.evidence_count,
    )


def _transition_recommendation(
    item: PersonaTransitionCandidate,
) -> SystemPersonaRecommendation:
    return _recommendation(
        target_kind="transition",
        target_id=_transition_target_id(item),
        action="defer_scope_required",
        rationale="contextual_transition_scope_unknown",
        evidence_count=2,
    )


def _recommendation(
    *,
    target_kind: RecommendationTargetKind,
    target_id: str,
    action: RecommendationAction,
    rationale: RecommendationRationale,
    evidence_count: int,
) -> SystemPersonaRecommendation:
    use: RecommendationUse = (
        "shadow_simulation_only"
        if action == "simulate_as_hypothesis"
        else "review_prioritization_only"
    )
    identity = {
        "target_kind": target_kind,
        "target_id": target_id,
        "action": action,
        "rationale": rationale,
        "evidence_count": evidence_count,
        "scope_status": "not_established",
        "currentness_status": "not_established",
        "use": use,
        "system_actor": "deterministic_policy/persona-adjudicator/0.1",
    }
    return SystemPersonaRecommendation(
        recommendation_id=canonical_sha256(identity),
        target_kind=target_kind,
        target_id=target_id,
        action=action,
        rationale=rationale,
        evidence_count=evidence_count,
        use=use,
    )


def _pattern_target_id(item: PersonaPatternCandidate) -> str:
    return canonical_sha256({"kind": "pattern", "candidate": item.model_dump(mode="json")})


def _transition_target_id(item: PersonaTransitionCandidate) -> str:
    return canonical_sha256({"kind": "transition", "candidate": item.model_dump(mode="json")})


def _omitted_count(
    evolution: PersonaEvolutionProfile,
    recommendations: tuple[SystemPersonaRecommendation, ...],
) -> int:
    source_total = (
        evolution.total_pattern_candidate_count + evolution.total_transition_candidate_count
    )
    return source_total - len(recommendations)


def _projection_status(
    evolution: PersonaEvolutionProfile,
    recommendations: tuple[SystemPersonaRecommendation, ...],
) -> str:
    return "complete" if _omitted_count(evolution, recommendations) == 0 else "bounded_partial"
