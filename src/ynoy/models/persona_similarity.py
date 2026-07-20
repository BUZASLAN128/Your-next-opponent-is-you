from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import DecisionLabel, StrictModel
from ynoy.util import canonical_sha256, sha256_text

type Digest = str
type SimilarityArm = Literal["generic", "retrieval", "structured"]
type SimilarityStatus = Literal[
    "invalid_target_isolation",
    "insufficient_labels",
    "contaminated",
    "proxy_only",
    "inconclusive",
]


class SimilaritySource(StrictModel):
    source_id: str = Field(min_length=1, max_length=256)
    source_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    text: str = Field(min_length=1, max_length=16_384)

    @model_validator(mode="after")
    def source_hash_matches_text(self) -> SimilaritySource:
        if self.source_sha256 != sha256_text(self.text):
            raise ValueError("similarity source hash does not match text")
        return self


class SimilarityCase(StrictModel):
    case_id: str = Field(min_length=1, max_length=256)
    cluster_id: str = Field(min_length=1, max_length=256)
    prompt_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_neighbor_sha256s: tuple[Digest, ...] = Field(max_length=128)
    target_isolated: bool
    prospective: bool

    @model_validator(mode="after")
    def neighbors_are_unique(self) -> SimilarityCase:
        if self.source_neighbor_sha256s != tuple(sorted(set(self.source_neighbor_sha256s))):
            raise ValueError("similarity source neighbors must be canonical and unique")
        return self


class SimilarityPrediction(StrictModel):
    case_id: str = Field(min_length=1, max_length=256)
    arm: SimilarityArm
    response_text: str = Field(min_length=1, max_length=8_192)
    decision_label: DecisionLabel
    frozen_before_target: bool
    target_seen: Literal[False] = False


class SimilarityLabel(StrictModel):
    case_id: str = Field(min_length=1, max_length=256)
    decision_label: DecisionLabel
    sealed_after_freeze: bool
    represented_user_authenticated: bool


class SimilaritySpec(StrictModel):
    minimum_cases: int = Field(default=18, ge=1, le=256)
    minimum_clusters: int = Field(default=8, ge=1, le=64)
    ngram_size: int = Field(default=5, ge=2, le=12)
    max_source_overlap: float = Field(default=0.45, ge=0.0, le=1.0)


class PersonaSimilarityAudit(StrictModel):
    protocol_version: Literal["persona-similarity-audit/0.1"] = "persona-similarity-audit/0.1"
    status: SimilarityStatus
    reason: str = Field(min_length=1, max_length=512)
    eligible_case_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    contaminated_case_ids: tuple[str, ...]
    exact_copy_case_ids: tuple[str, ...]
    max_source_overlap: dict[SimilarityArm, float]
    arm_decision_accuracy: dict[SimilarityArm, float | None]
    prospective_authenticated_labels_used: bool
    persona_quality_claimed: Literal[False] = False
    audit_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def audit_is_canonical(self) -> PersonaSimilarityAudit:
        expected = {"generic", "retrieval", "structured"}
        if set(self.max_source_overlap) != expected or set(self.arm_decision_accuracy) != expected:
            raise ValueError("similarity audit arms are incomplete")
        if self.contaminated_case_ids != tuple(sorted(set(self.contaminated_case_ids))):
            raise ValueError("contaminated similarity cases must be canonical")
        if self.exact_copy_case_ids != tuple(sorted(set(self.exact_copy_case_ids))):
            raise ValueError("exact-copy similarity cases must be canonical")
        payload = self.model_dump(mode="json", exclude={"audit_sha256"})
        if self.audit_sha256 != canonical_sha256(payload):
            raise ValueError("similarity audit hash does not match its payload")
        return self
