from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import DecisionLabel, Mode, StrictModel
from ynoy.models.canonical import CanonicalClaim
from ynoy.models.review_vocab import TargetLayer
from ynoy.util import canonical_sha256

type Sha256Digest = str


class JudgmentBasis(StrEnum):
    EXPLICIT_POLICY = "explicitPolicy"
    INFERRED_PERSONA = "inferredPersona"
    GENERIC_ADVISOR = "genericAdvisor"
    ABSTENTION = "abstention"


class ConflictRelation(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class DecisionGroupKey(StrictModel):
    subject_id: str = Field(min_length=1)
    target_layer: TargetLayer
    reviewed_decision_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def identifiers_are_canonical(self) -> DecisionGroupKey:
        values = (self.subject_id, self.reviewed_decision_key)
        if any(value != value.strip() for value in values):
            raise ValueError("decision group identifiers must be trimmed")
        return self


class CanonicalClaimIdentity(StrictModel):
    claim_id: UUID
    subject_id: str = Field(min_length=1)
    target_layer: TargetLayer
    reviewed_decision_key: str = Field(min_length=1)
    claim_tuple_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    decision_key_receipt_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    identity_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def identity_is_canonical(self) -> CanonicalClaimIdentity:
        if self.subject_id != self.subject_id.strip():
            raise ValueError("canonical identity subject must be trimmed")
        if self.reviewed_decision_key != self.reviewed_decision_key.strip():
            raise ValueError("reviewed decision key must be trimmed")
        if self.identity_sha256 != canonical_identity_digest(self):
            raise ValueError("canonical identity hash does not match its payload")
        return self

    @property
    def full_key(self) -> DecisionGroupKey:
        return DecisionGroupKey(
            subject_id=self.subject_id,
            target_layer=self.target_layer,
            reviewed_decision_key=self.reviewed_decision_key,
        )


class AdmittedDecisionClaim(StrictModel):
    claim: CanonicalClaim
    identity: CanonicalClaimIdentity

    @model_validator(mode="after")
    def identity_binds_claim(self) -> AdmittedDecisionClaim:
        expected = (
            self.claim.record_id,
            self.claim.subject_id,
            self.claim.target_layer,
            self.claim.claim_sha256,
        )
        actual = (
            self.identity.claim_id,
            self.identity.subject_id,
            self.identity.target_layer,
            self.identity.claim_tuple_sha256,
        )
        if actual != expected:
            raise ValueError("canonical identity does not bind the immutable claim tuple")
        return self


class SupersessionBinding(StrictModel):
    successor_claim_id: UUID
    predecessor_claim_id: UUID
    successor_tuple_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    predecessor_tuple_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    full_key: DecisionGroupKey
    review_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    expected_head: int = Field(ge=0)
    receipt_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def binding_is_canonical(self) -> SupersessionBinding:
        if self.successor_claim_id == self.predecessor_claim_id:
            raise ValueError("supersession endpoints must be distinct")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("supersession receipt hash does not match its payload")
        return self


class ConflictAssessment(StrictModel):
    left_claim_id: UUID
    right_claim_id: UUID
    full_key: DecisionGroupKey
    relation: ConflictRelation
    evidence_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def pair_is_canonical(self) -> ConflictAssessment:
        if self.left_claim_id == self.right_claim_id:
            raise ValueError("conflict assessment requires two distinct claims")
        if str(self.left_claim_id) > str(self.right_claim_id):
            raise ValueError("conflict assessment claim pair must use canonical order")
        if self.reason != self.reason.strip():
            raise ValueError("conflict assessment reason must be trimmed")
        return self


class RequiredDecisionGroups(StrictModel):
    version: str = Field(min_length=1)
    groups: tuple[DecisionGroupKey, ...]
    manifest_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def manifest_is_canonical(self) -> RequiredDecisionGroups:
        if self.version != self.version.strip():
            raise ValueError("decision-group manifest version must be trimmed")
        keys = tuple(_group_sort_key(item) for item in self.groups)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("decision-group manifest must be sorted and unique")
        payload = self.model_dump(mode="json", exclude={"manifest_sha256"})
        if self.manifest_sha256 != canonical_sha256(payload):
            raise ValueError("decision-group manifest hash does not match its payload")
        return self


class MirrorCandidate(StrictModel):
    full_target: DecisionGroupKey
    predicted_label: DecisionLabel
    ranking_score: float = Field(ge=0.0, le=1.0)
    predictor_version: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    stratum: str = Field(min_length=1)


class ExplicitPolicyJudgment(StrictModel):
    basis: Literal[JudgmentBasis.EXPLICIT_POLICY] = JudgmentBasis.EXPLICIT_POLICY
    mode: Literal[Mode.MIRROR] = Mode.MIRROR
    decision_label: DecisionLabel
    claim_ids: tuple[UUID, ...] = Field(min_length=1)


class InferredPersonaJudgment(StrictModel):
    basis: Literal[JudgmentBasis.INFERRED_PERSONA] = JudgmentBasis.INFERRED_PERSONA
    mode: Literal[Mode.MIRROR] = Mode.MIRROR
    decision_label: DecisionLabel
    calibrated_probability: float = Field(ge=0.0, le=1.0)
    calibration_profile_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    claim_ids: tuple[UUID, ...] = Field(min_length=1)


class GenericAdvisorJudgment(StrictModel):
    basis: Literal[JudgmentBasis.GENERIC_ADVISOR] = JudgmentBasis.GENERIC_ADVISOR
    mode: Literal[Mode.ADVISOR] = Mode.ADVISOR
    advice_code: Literal["generic_reversible_guidance"] = "generic_reversible_guidance"


class AbstentionJudgment(StrictModel):
    basis: Literal[JudgmentBasis.ABSTENTION] = JudgmentBasis.ABSTENTION
    mode: Mode
    reason: str = Field(min_length=1)
    unknowns: tuple[str, ...] = Field(min_length=1)


type PublicJudgment = Annotated[
    ExplicitPolicyJudgment | InferredPersonaJudgment | GenericAdvisorJudgment | AbstentionJudgment,
    Field(discriminator="basis"),
]


def canonical_identity_digest(identity: CanonicalClaimIdentity) -> str:
    return canonical_sha256(identity.model_dump(mode="json", exclude={"identity_sha256"}))


def _group_sort_key(key: DecisionGroupKey) -> tuple[str, str, str]:
    return (key.subject_id, key.target_layer.value, key.reviewed_decision_key)
