from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_evolution import EvidenceStrength
from ynoy.util import canonical_sha256

type Digest = str
type RecommendationAction = Literal[
    "simulate_as_hypothesis",
    "prioritize_for_review",
    "defer_more_evidence",
    "defer_scope_required",
]
type RecommendationUse = Literal["shadow_simulation_only", "review_prioritization_only"]
type RecommendationTargetKind = Literal["pattern", "transition"]
type RecommendationRationale = Literal[
    "high_repetition_direct_evidence",
    "repeated_direct_evidence",
    "weak_repetition_only",
    "contextual_transition_scope_unknown",
]


class SystemPersonaRecommendation(StrictModel):
    recommendation_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    target_kind: RecommendationTargetKind
    target_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    action: RecommendationAction
    rationale: RecommendationRationale
    evidence_count: int = Field(ge=2)
    scope_status: Literal["not_established"] = "not_established"
    currentness_status: Literal["not_established"] = "not_established"
    use: RecommendationUse
    system_actor: Literal["deterministic_policy/persona-adjudicator/0.1"] = (
        "deterministic_policy/persona-adjudicator/0.1"
    )
    user_adoption: Literal["not_provided"] = "not_provided"
    semantic_adoption: Literal["not_established"] = "not_established"
    adopted: Literal[False] = False
    core_eligible: Literal[False] = False
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def recommendation_is_consistent(self) -> SystemPersonaRecommendation:
        expected_rationale = {
            "simulate_as_hypothesis": "high_repetition_direct_evidence",
            "prioritize_for_review": "repeated_direct_evidence",
            "defer_more_evidence": "weak_repetition_only",
            "defer_scope_required": "contextual_transition_scope_unknown",
        }[self.action]
        if self.rationale != expected_rationale:
            raise ValueError("system recommendation action contradicts its rationale")
        if (self.target_kind == "transition") != (self.action == "defer_scope_required"):
            raise ValueError("system recommendation action contradicts its target kind")
        expected_use = (
            "shadow_simulation_only"
            if self.action == "simulate_as_hypothesis"
            else "review_prioritization_only"
        )
        if self.use != expected_use:
            raise ValueError("system recommendation action contradicts its allowed use")
        expected_id = canonical_sha256(
            {
                "target_kind": self.target_kind,
                "target_id": self.target_id,
                "action": self.action,
                "rationale": self.rationale,
                "evidence_count": self.evidence_count,
                "scope_status": self.scope_status,
                "currentness_status": self.currentness_status,
                "use": self.use,
                "system_actor": self.system_actor,
            }
        )
        if self.recommendation_id != expected_id:
            raise ValueError("system recommendation identifier is invalid")
        return self


def pattern_recommendation_disposition(
    strength: EvidenceStrength,
) -> tuple[RecommendationAction, RecommendationRationale]:
    """Map evidence strength to a bounded recommendation, never adoption."""
    if strength == "high_repetition":
        return "simulate_as_hypothesis", "high_repetition_direct_evidence"
    if strength == "repeated":
        return "prioritize_for_review", "repeated_direct_evidence"
    return "defer_more_evidence", "weak_repetition_only"


class PersonaAdjudicationProfile(StrictModel):
    protocol_version: Literal["persona-adjudication/0.2"] = "persona-adjudication/0.2"
    pack_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evolution_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_pattern_candidate_count: int = Field(ge=0)
    source_transition_candidate_count: int = Field(ge=0)
    omitted_candidate_count: int = Field(ge=0)
    review_projection_status: Literal["complete", "bounded_partial"]
    review_projection_exhaustive: bool
    recommendations: tuple[SystemPersonaRecommendation, ...] = Field(max_length=128)
    represented_user_review: Literal["not_performed"] = "not_performed"
    verified_adoption_available: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    authority: Literal["none"] = "none"
    adjudication_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_is_canonical(self) -> PersonaAdjudicationProfile:
        keys = tuple((item.target_kind, item.target_id) for item in self.recommendations)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("system recommendations must be sorted and target-unique")
        represented = len(self.recommendations)
        source_total = self.source_pattern_candidate_count + self.source_transition_candidate_count
        if self.omitted_candidate_count != source_total - represented:
            raise ValueError("system adjudication omitted count is inconsistent")
        expected_exhaustive = self.omitted_candidate_count == 0
        if self.review_projection_exhaustive != expected_exhaustive:
            raise ValueError("system adjudication exhaustiveness is inconsistent")
        expected_status = "complete" if expected_exhaustive else "bounded_partial"
        if self.review_projection_status != expected_status:
            raise ValueError("system adjudication projection status is inconsistent")
        payload = self.model_dump(mode="json", exclude={"adjudication_sha256"})
        if self.adjudication_sha256 != canonical_sha256(payload):
            raise ValueError("persona adjudication hash does not match")
        return self
