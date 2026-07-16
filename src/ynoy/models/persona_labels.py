from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import CandidateKind, StrictModel
from ynoy.util import canonical_sha256


class LabelAuthorship(StrEnum):
    SELF = "self"
    QUOTED_OR_PASTED = "quoted_or_pasted"
    MIXED = "mixed"
    OTHER = "other"
    UNKNOWN = "unknown"


class LabelClaimHolder(StrEnum):
    SELF = "self"
    ASSISTANT = "assistant"
    THIRD_PARTY = "third_party"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class LabelAdoption(StrEnum):
    ENDORSED = "endorsed"
    REJECTED = "rejected"
    HYPOTHETICAL = "hypothetical"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class AnnotationDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    CORRECT = "correct"
    DEFER = "defer"
    ASK = "ask"
    NONE = "none"
    UNKNOWN = "unknown"


class AnnotationTargetLayer(StrEnum):
    PERSONA = "persona"
    PROJECT_RULE = "project_rule"
    ARCHITECTURE = "architecture"
    MISSION = "mission"
    EPISODIC = "episodic"
    RESEARCH = "research"
    NONE = "none"
    UNKNOWN = "unknown"


class LabelConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ExactTextSpan(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_bounds(self) -> ExactTextSpan:
        if self.end <= self.start or len(self.text) != self.end - self.start:
            raise ValueError("label span bounds must match its exact text length")
        return self


class AnnotationScope(StrictModel):
    project: str | None = None
    role: str | None = None
    audience: str | None = None
    risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    temporal: str | None = None

    @model_validator(mode="after")
    def scoped_text_is_trimmed(self) -> AnnotationScope:
        values = (self.project, self.role, self.audience, self.temporal)
        if any(
            value is not None and (not value.strip() or value != value.strip()) for value in values
        ):
            raise ValueError("label scope text must be non-empty and trimmed")
        return self


class PersonaAnnotationJudgment(StrictModel):
    authorship: LabelAuthorship
    claim_holder: LabelClaimHolder
    adoption: LabelAdoption
    decision: AnnotationDecision
    target_layer: AnnotationTargetLayer
    persona_kind: CandidateKind | None = None
    scope: AnnotationScope
    rationale_spans: tuple[ExactTextSpan, ...] = ()
    evidence_demand_spans: tuple[ExactTextSpan, ...] = ()
    should_abstain: bool
    exclude_from_persona: bool
    exclusion_reason: str | None = Field(default=None, min_length=1)
    confidence: LabelConfidence
    notes: str | None = None

    @model_validator(mode="after")
    def identity_safety_is_consistent(self) -> PersonaAnnotationJudgment:
        ambiguous = (
            self.authorship != LabelAuthorship.SELF
            or self.claim_holder != LabelClaimHolder.SELF
            or self.adoption != LabelAdoption.ENDORSED
        )
        unknown = (
            self.authorship == LabelAuthorship.UNKNOWN
            or self.claim_holder == LabelClaimHolder.UNKNOWN
            or self.adoption == LabelAdoption.UNKNOWN
            or self.decision == AnnotationDecision.UNKNOWN
            or self.target_layer == AnnotationTargetLayer.UNKNOWN
            or self.confidence == LabelConfidence.UNKNOWN
        )
        if (ambiguous or unknown) and not self.exclude_from_persona:
            raise ValueError("ambiguous or non-endorsed text must stay outside persona")
        if unknown and not self.should_abstain:
            raise ValueError("unknown identity or decision fields require abstention")
        if self.exclude_from_persona != bool(self.exclusion_reason):
            raise ValueError("persona exclusion requires exactly one non-empty reason")
        if self.target_layer != AnnotationTargetLayer.PERSONA and self.persona_kind is not None:
            raise ValueError("persona kind is valid only for the persona target layer")
        if (
            self.target_layer == AnnotationTargetLayer.PERSONA
            and not self.exclude_from_persona
            and self.persona_kind is None
        ):
            raise ValueError("included persona labels require a persona kind")
        return self


class PersonaAnnotationLabel(PersonaAnnotationJudgment):
    presentation_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class CompletedPersonaLabelSet(StrictModel):
    schema_version: Literal["persona-labels/0.1"] = "persona-labels/0.1"
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_by: Literal["represented_user"]
    instructions: tuple[str, ...]
    allowed_values: dict[str, tuple[str, ...]]
    labels: tuple[PersonaAnnotationLabel, ...] = Field(min_length=32, max_length=32)

    @model_validator(mode="after")
    def labels_are_unique(self) -> CompletedPersonaLabelSet:
        identifiers = tuple(item.presentation_id for item in self.labels)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("completed labels must have unique presentation identifiers")
        return self


class SealedPersonaLabel(StrictModel):
    window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_partition: Literal["annotation_development", "annotation_reserved"]
    source_presentation_ids: tuple[str, ...] = Field(min_length=1, max_length=2)
    judgment: PersonaAnnotationJudgment
    interpretation_authority: Literal["represented_user_local_attestation"] = (
        "represented_user_local_attestation"
    )
    identity_authentication: Literal["local_operator_attestation_not_cryptographic"] = (
        "local_operator_attestation_not_cryptographic"
    )
    core_eligible: Literal[False] = False
    automatic_core_promotion: Literal[False] = False


class PersonaLabelSealReceipt(StrictModel):
    protocol_version: Literal["persona-label-seal/0.1"] = "persona-label-seal/0.1"
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    label_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    presentation_count: Literal[32] = 32
    unique_window_count: Literal[24] = 24
    repeat_pair_count: Literal[8] = 8
    initial_submission_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_repeat_exact_match_count: int = Field(ge=0, le=8)
    adjudicated_repeat_pair_count: int = Field(ge=0, le=8)
    adjudication_set_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    initial_field_agreement_counts: dict[str, int]
    excluded_from_persona_count: int = Field(ge=0, le=24)
    abstained_count: int = Field(ge=0, le=24)
    persona_candidate_count: int = Field(ge=0, le=24)
    interpretation_authority: Literal["represented_user_local_attestation"] = (
        "represented_user_local_attestation"
    )
    identity_authentication: Literal["local_operator_attestation_not_cryptographic"] = (
        "local_operator_attestation_not_cryptographic"
    )
    persona_quality_claimed: Literal[False] = False
    protected_holdout_used: Literal[False] = False
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> PersonaLabelSealReceipt:
        if self.initial_repeat_exact_match_count + self.adjudicated_repeat_pair_count != 8:
            raise ValueError("sealed labels must resolve every initial repeat pair")
        if bool(self.adjudication_set_sha256) != bool(self.adjudicated_repeat_pair_count):
            raise ValueError("final receipt adjudication link is inconsistent")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("persona label seal receipt does not match its payload")
        return self
