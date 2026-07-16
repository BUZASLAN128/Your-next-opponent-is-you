from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import (
    CandidateKind,
    CandidateStatus,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    RecordBase,
    ScopeRef,
)
from ynoy.util import new_id


class ClaimCandidate(RecordBase):
    subject_id: str = "self"
    claim_holder: ClaimHolder
    kind: CandidateKind
    proposition: str
    scope: ScopeRef = Field(default_factory=ScopeRef)
    confidence: float = Field(ge=0.0, le=1.0)
    status: CandidateStatus = CandidateStatus.PROPOSED
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    origin_cluster_ids: tuple[str, ...]
    revision_of: UUID | None = None
    superseded_by: UUID | None = None

    @model_validator(mode="after")
    def subject_matches_scope(self) -> ClaimCandidate:
        if not self.subject_id.strip() or self.subject_id != self.subject_id.strip():
            raise ValueError("claim candidate subject must be a trimmed identifier")
        if self.scope.person_id != self.subject_id:
            raise ValueError("claim candidate subject must match scope person")
        return self


class DecisionEvent(RecordBase):
    subject_id: str = "self"
    source_event_id: UUID
    label: DecisionLabel
    target_locator: str | None = None
    rationale: str | None = None
    rationale_is_inferred: bool = False
    demanded_evidence: tuple[str, ...] = ()
    scope: ScopeRef = Field(default_factory=ScopeRef)


class IdentityCandidate(RecordBase):
    subject_id: str = "self"
    view: Literal["trait", "value", "narrative", "metacognition"]
    proposition: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: CandidateStatus = CandidateStatus.PROPOSED
    scope: ScopeRef = Field(default_factory=ScopeRef)
    origin_cluster_ids: tuple[str, ...]


class ContinuityEvent(RecordBase):
    subject_id: str = "self"
    event_type: Literal["reinforced", "corrected", "contradicted", "superseded", "unknown"]
    earlier_record_id: UUID
    later_record_id: UUID
    explanation: str | None = None
    effective_at: datetime | None = None


class DerivationEdge(RecordBase):
    source_record_id: UUID
    derived_record_id: UUID
    relation: Literal[
        "derived_from",
        "quoted_from",
        "attributed_to",
        "revision_of",
        "invalidates",
        "supports",
        "contradicts",
    ]
    origin_cluster_id: str


class ControlRecord(RecordBase):
    subject_id: str = "self"
    instruction: str
    scope: ScopeRef = Field(default_factory=ScopeRef)
    authority: Literal["remember", "predict", "recommend", "review"]
    status: CandidateStatus = CandidateStatus.CONFIRMED
    source_event_id: UUID


class BootstrapDeclaration(RecordBase):
    source_record_id: UUID = Field(default_factory=new_id)
    subject_id: str = "self"
    kind: CandidateKind
    statement: str
    scope: ScopeRef = Field(default_factory=ScopeRef)
    decision_label: DecisionLabel | None = None
    source_name: str
    data_class: DataClass = DataClass.DERIVED_IDENTITY
    synthetic: bool = False
    status: CandidateStatus = CandidateStatus.CONFIRMED

    @model_validator(mode="after")
    def classification_is_honest(self) -> BootstrapDeclaration:
        if not self.subject_id.strip() or self.subject_id != self.subject_id.strip():
            raise ValueError("bootstrap declaration subject must be a trimmed identifier")
        if self.scope.person_id != self.subject_id:
            raise ValueError("bootstrap declaration subject must match scope person")
        if self.synthetic and self.data_class != DataClass.PUBLIC_SYNTHETIC:
            raise ValueError("synthetic bootstrap declarations must use D0")
        if not self.synthetic and self.data_class != DataClass.DERIVED_IDENTITY:
            raise ValueError("real bootstrap declarations are sensitive D3 data")
        return self
