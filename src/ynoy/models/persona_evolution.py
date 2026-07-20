from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.util import canonical_sha256

type Digest = str
type EvolutionDimension = Literal["planning_mode", "workflow_control", "resource_strategy"]
type EvolutionState = Literal[
    "plan_first",
    "execute_now",
    "autonomous_momentum",
    "user_gate",
    "bounded_resources",
    "exhaustive_processing",
]
type EvidenceStrength = Literal["weak_repetition", "repeated", "high_repetition"]


class EvolutionEvidenceRef(StrictModel):
    atom_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    source_role: Literal["direct_user_expression"] = "direct_user_expression"


class PersonaPatternCandidate(StrictModel):
    key: str = Field(min_length=1, max_length=64)
    guidance: str = Field(min_length=1, max_length=256)
    evidence_count: int = Field(ge=2)
    distinct_atom_count: int = Field(ge=1)
    first_observed_at: datetime
    last_observed_at: datetime
    evidence_strength: EvidenceStrength
    evidence_refs: tuple[EvolutionEvidenceRef, ...] = Field(min_length=1, max_length=8)
    scope_status: Literal["not_established"] = "not_established"
    status: Literal["derived_unadopted"] = "derived_unadopted"
    use: Literal["proposal_context_only"] = "proposal_context_only"
    adopted: Literal[False] = False
    core_eligible: Literal[False] = False
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def interval_is_valid(self) -> PersonaPatternCandidate:
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("persona pattern interval is invalid")
        if self.distinct_atom_count < len(self.evidence_refs):
            raise ValueError("persona pattern evidence inventory is inconsistent")
        if self.distinct_atom_count > self.evidence_count:
            raise ValueError("persona pattern atom count exceeds its evidence count")
        receipts = tuple(item.evidence_receipt for item in self.evidence_refs)
        if len(receipts) != len(set(receipts)):
            raise ValueError("persona pattern evidence receipts must be unique")
        return self


class PersonaTransitionCandidate(StrictModel):
    dimension: EvolutionDimension
    from_state: EvolutionState
    to_state: EvolutionState
    transition_at: datetime
    from_evidence: EvolutionEvidenceRef
    to_evidence: EvolutionEvidenceRef
    scope_status: Literal["not_established"] = "not_established"
    status: Literal["contextual_transition_candidate"] = "contextual_transition_candidate"
    use: Literal["proposal_context_only"] = "proposal_context_only"
    semantic_adoption: Literal["not_established"] = "not_established"
    adopted: Literal[False] = False
    core_eligible: Literal[False] = False
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def transition_changes_state(self) -> PersonaTransitionCandidate:
        if self.from_state == self.to_state:
            raise ValueError("persona transition must change state")
        if self.transition_at != self.to_evidence.observed_at:
            raise ValueError("persona transition timestamp is not evidence-bound")
        if self.from_evidence.observed_at > self.to_evidence.observed_at:
            raise ValueError("persona transition evidence is not chronological")
        if self.from_evidence.evidence_receipt == self.to_evidence.evidence_receipt:
            raise ValueError("persona transition requires two distinct observations")
        allowed = {
            "planning_mode": {"plan_first", "execute_now"},
            "workflow_control": {"autonomous_momentum", "user_gate"},
            "resource_strategy": {"bounded_resources", "exhaustive_processing"},
        }
        if (
            self.from_state not in allowed[self.dimension]
            or self.to_state not in allowed[self.dimension]
        ):
            raise ValueError("persona transition state does not match its dimension")
        return self


class PersonaEvolutionProfile(StrictModel):
    protocol_version: Literal["persona-evolution/0.1"] = "persona-evolution/0.1"
    pack_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    total_pattern_candidate_count: int = Field(ge=0)
    total_transition_candidate_count: int = Field(ge=0)
    patterns: tuple[PersonaPatternCandidate, ...] = Field(max_length=64)
    transitions: tuple[PersonaTransitionCandidate, ...] = Field(max_length=64)
    unknowns: tuple[str, ...]
    model_enrichment: Literal["not_used"] = "not_used"
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    authority: Literal["none"] = "none"
    evolution_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_is_canonical(self) -> PersonaEvolutionProfile:
        if self.total_pattern_candidate_count < len(self.patterns):
            raise ValueError("persona pattern candidate count is inconsistent")
        if self.total_transition_candidate_count < len(self.transitions):
            raise ValueError("persona transition candidate count is inconsistent")
        keys = tuple(item.key for item in self.patterns)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("persona pattern candidates must be sorted and unique")
        if len(self.unknowns) != len(set(self.unknowns)):
            raise ValueError("persona evolution unknowns must be unique")
        payload = self.model_dump(mode="json", exclude={"evolution_sha256"})
        if self.evolution_sha256 != canonical_sha256(payload):
            raise ValueError("persona evolution hash does not match")
        return self
