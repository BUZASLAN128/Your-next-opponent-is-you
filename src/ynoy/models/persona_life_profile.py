from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ynoy.full_persona.identity_rules import LIFE_TOPIC_ORDER, LifeTopic
from ynoy.models.base import DataClass, StrictModel
from ynoy.util import canonical_sha256

type Digest = str
type LifeClaim = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]
type UnknownCode = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=128)
]


class PersonaLifeSupport(StrictModel):
    evidence_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    support_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def support_is_canonical(self) -> PersonaLifeSupport:
        payload = self.model_dump(mode="json", exclude={"support_sha256"})
        if self.support_sha256 != canonical_sha256(payload):
            raise ValueError("life candidate support hash does not match")
        return self


class PersonaLifeCandidate(StrictModel):
    topic: LifeTopic
    semantic_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    claim: LifeClaim
    supports: tuple[PersonaLifeSupport, ...] = Field(min_length=1, max_length=64)
    support_count: int = Field(ge=1)
    support_projection_exhaustive: bool
    first_observed_at: datetime
    last_observed_at: datetime
    observation_count: int = Field(ge=1)
    source_role: Literal["direct_user_expression"] = "direct_user_expression"
    truth_status: Literal["observed_unadopted"] = "observed_unadopted"
    semantic_adoption: Literal["not_established"] = "not_established"
    core_eligible: Literal[False] = False
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def candidate_is_canonical(self) -> PersonaLifeCandidate:
        if self.first_observed_at > self.last_observed_at:
            raise ValueError("life candidate observation interval is invalid")
        if self.support_count != self.observation_count or self.support_count < len(self.supports):
            raise ValueError("life candidate support count is inconsistent")
        expected_exhaustive = self.support_count == len(self.supports)
        if self.support_projection_exhaustive != expected_exhaustive:
            raise ValueError("life candidate support projection is inconsistent")
        support_ids = tuple(item.evidence_id for item in self.supports)
        if support_ids != tuple(sorted(set(support_ids))):
            raise ValueError("life candidate supports must be sorted and unique")
        if self.semantic_sha256 != canonical_sha256(
            {"topic": self.topic, "claim": " ".join(self.claim.casefold().split())}
        ):
            raise ValueError("life candidate semantic identifier is invalid")
        return self


class PersonaLifeTopic(StrictModel):
    key: LifeTopic
    evidence_state: Literal["literal_candidates", "unknown"]
    matched_evidence_count: int = Field(ge=0)
    unique_candidate_count: int = Field(ge=0)
    candidates: tuple[PersonaLifeCandidate, ...] = Field(max_length=8)
    unknowns: tuple[UnknownCode, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def topic_is_canonical(self) -> PersonaLifeTopic:
        if self.unique_candidate_count < len(self.candidates):
            raise ValueError("life topic candidate count is inconsistent")
        if any(item.topic != self.key for item in self.candidates):
            raise ValueError("life topic contains a candidate from another topic")
        expected = "literal_candidates" if self.candidates else "unknown"
        if self.evidence_state != expected:
            raise ValueError("life topic evidence state is inconsistent")
        return self


class PersonaLifeProfile(StrictModel):
    protocol_version: Literal["persona-life-profile/0.1"] = "persona-life-profile/0.1"
    profile_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    expires_at: datetime
    data_class: DataClass
    synthetic: bool
    scanned_evidence_count: int = Field(ge=0)
    topics: tuple[PersonaLifeTopic, ...] = Field(min_length=5, max_length=5)
    source_scan_status: Literal["complete_verified"] = "complete_verified"
    matcher_coverage: Literal["all_verified_evidence"] = "all_verified_evidence"
    semantic_exhaustive: Literal[False] = False
    identity_fact_policy: Literal["literal_direct_evidence_or_unknown"] = (
        "literal_direct_evidence_or_unknown"
    )
    model_enrichment: Literal["not_used"] = "not_used"
    target_data_used: Literal[False] = False
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    semantic_adoption: Literal["not_established"] = "not_established"
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    authority: Literal["none"] = "none"
    profile_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_is_canonical(self) -> PersonaLifeProfile:
        if tuple(item.key for item in self.topics) != LIFE_TOPIC_ORDER:
            raise ValueError("life profile topic order changed")
        expected_class = (
            DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.DERIVED_IDENTITY
        )
        if self.data_class != expected_class:
            raise ValueError("life profile data class contradicts its mode")
        expected_id = canonical_sha256(
            {
                "source_head_sha256": self.source_head_sha256,
                "topics": [item.model_dump(mode="json") for item in self.topics],
            }
        )
        if self.profile_id != expected_id:
            raise ValueError("life profile identifier is invalid")
        payload = self.model_dump(mode="json", exclude={"profile_sha256"})
        if self.profile_sha256 != canonical_sha256(payload):
            raise ValueError("life profile hash does not match")
        return self
