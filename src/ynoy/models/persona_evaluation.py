from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.persona_labels import AnnotationDecision
from ynoy.util import canonical_sha256, sha256_text

PersonaBaselineName = Literal[
    "zero_abstain",
    "low_recent3",
    "history_frequency",
    "history_lexical",
    "history_declared",
    "history_structured",
]


class PersonaHistoryEvidence(StrictModel):
    evidence_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    decision: AnnotationDecision
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lexical_text: str = Field(min_length=1)
    source_receipts: tuple[str, ...] = Field(min_length=1)
    scope_key: str | None = None
    declared: bool = False
    persona_included: bool = False

    @model_validator(mode="after")
    def context_receipt_matches(self) -> PersonaHistoryEvidence:
        if self.context_sha256 != sha256_text(self.lexical_text):
            raise ValueError("history context receipt does not match its lexical text")
        return self


class PersonaEvaluationCase(StrictModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_context: str = Field(min_length=1)
    source_receipts: tuple[str, ...] = Field(min_length=1)
    scope_key: str | None = None
    data_class: DataClass
    synthetic: bool
    target_visible_to_predictor: Literal[False] = False

    @model_validator(mode="after")
    def source_mode_matches(self) -> PersonaEvaluationCase:
        expected = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.data_class != expected:
            raise ValueError("evaluation case data class contradicts its source mode")
        if self.context_sha256 != sha256_text(self.task_context):
            raise ValueError("evaluation case receipt does not match its task context")
        return self


class PersonaEvaluationTarget(StrictModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: AnnotationDecision
    authority: Literal["synthetic_fixture", "represented_user"]

    @model_validator(mode="after")
    def target_is_scorable(self) -> PersonaEvaluationTarget:
        if self.decision in {AnnotationDecision.NONE, AnnotationDecision.UNKNOWN}:
            raise ValueError("evaluation targets must use a scorable decision")
        return self


class PersonaBaselinePrediction(StrictModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline: PersonaBaselineName
    predicted_decision: AnnotationDecision
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool
    evidence_receipts: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    provenance_complete: bool
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def abstention_is_consistent(self) -> PersonaBaselinePrediction:
        expected = self.predicted_decision == AnnotationDecision.UNKNOWN
        if self.abstained != expected or self.provenance_complete != (
            self.abstained or bool(self.evidence_receipts)
        ):
            raise ValueError("baseline abstention or provenance is inconsistent")
        return self


class PersonaBaselineRun(StrictModel):
    protocol_version: Literal["persona-baselines/0.1"] = "persona-baselines/0.1"
    holdout_freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    deletion_proof_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    retention_expires_at: datetime
    case_count: int = Field(ge=1)
    target_count: int = Field(ge=1)
    duplicate_case_count: Literal[0] = 0
    exact_training_overlap_count: Literal[0] = 0
    protected_holdout: Literal[True] = True
    predictions: tuple[PersonaBaselinePrediction, ...] = Field(min_length=1)
    metrics: dict[str, dict[str, float | int]]
    target_authority: Literal["synthetic_fixture", "represented_user"]
    evidence_tier: Literal["mock/support", "live"]
    persona_quality_claimed: Literal[False] = False
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def run_contract_matches(self) -> PersonaBaselineRun:
        if self.case_count != self.target_count:
            raise ValueError("every evaluation case requires one target")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"run_sha256"}))
        if self.run_sha256 != expected:
            raise ValueError("persona baseline run receipt does not match its payload")
        return self
