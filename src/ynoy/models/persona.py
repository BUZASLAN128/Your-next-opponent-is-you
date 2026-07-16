from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import (
    CandidateKind,
    CandidateStatus,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    EvidenceRegime,
    ScopeRef,
    SourceAuthority,
    Speaker,
    StrictModel,
)
from ynoy.models.manager import OperatingMemorySeed


class PersonaViewName(StrEnum):
    BEHAVIORAL_PATTERNS = "behavioral_patterns"
    VALUES = "values"
    AUTOBIOGRAPHICAL = "autobiographical_continuity"
    PERSONAL_METACOGNITION = "personal_metacognition"


class AdoptedPersonaDeclaration(StrictModel):
    record_id: UUID
    source_record_id: UUID
    source_name: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    speaker: Literal[Speaker.USER] = Speaker.USER
    claim_holder: Literal[ClaimHolder.REPRESENTED_USER] = ClaimHolder.REPRESENTED_USER
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    adopted: Literal[True] = True
    evidence_plane: Literal["identity_interpretation"] = "identity_interpretation"
    kind: CandidateKind
    statement: str = Field(min_length=1)
    scope: ScopeRef
    decision_label: DecisionLabel | None = None
    status: Literal[CandidateStatus.CONFIRMED] = CandidateStatus.CONFIRMED
    data_class: DataClass
    synthetic: bool

    @model_validator(mode="after")
    def attribution_and_classification_are_consistent(self) -> AdoptedPersonaDeclaration:
        if not self.subject_id.strip() or self.subject_id != self.subject_id.strip():
            raise ValueError("persona declaration subject must be a trimmed identifier")
        if self.scope.person_id != self.subject_id:
            raise ValueError("persona declaration subject must match scope person")
        if self.synthetic != (self.data_class == DataClass.PUBLIC_SYNTHETIC):
            raise ValueError("synthetic persona declarations must use D0")
        if not self.synthetic and self.data_class != DataClass.DERIVED_IDENTITY:
            raise ValueError("real persona declarations must use D3")
        return self


class PersonaFacet(StrictModel):
    record_id: UUID
    source_record_id: UUID
    source_name: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    speaker: Literal[Speaker.USER] = Speaker.USER
    claim_holder: Literal[ClaimHolder.REPRESENTED_USER] = ClaimHolder.REPRESENTED_USER
    adopted: Literal[True] = True
    evidence_plane: Literal["identity_interpretation"] = "identity_interpretation"
    kind: CandidateKind
    statement: str = Field(min_length=1)
    scope: ScopeRef
    decision_label: DecisionLabel | None = None
    status: Literal[CandidateStatus.CONFIRMED] = CandidateStatus.CONFIRMED
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    evidence_status: Literal["explicit_declaration"] = "explicit_declaration"
    validation_status: Literal["not_validated"] = "not_validated"
    data_class: DataClass


class PersonaView(StrictModel):
    name: PersonaViewName
    facets: tuple[PersonaFacet, ...] = ()


class PersonaPreview(StrictModel):
    status: Literal["preview"] = "preview"
    subject_id: str = Field(min_length=1)
    persona_state: Literal["declared_only"] = "declared_only"
    evidence_regime: Literal[EvidenceRegime.DECLARED] = EvidenceRegime.DECLARED
    confidence_status: Literal["low_unvalidated"] = "low_unvalidated"
    data_class: DataClass
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    source_receipts: tuple[UUID, ...] = Field(min_length=1)
    declaration_count: int = Field(ge=1)
    views: tuple[PersonaView, ...] = Field(min_length=4, max_length=4)
    scoped_objects: tuple[PersonaFacet, ...] = ()
    missing_views: tuple[PersonaViewName, ...] = ()
    operating_memory: OperatingMemorySeed
    unknowns: tuple[str, ...]
    scope_generalization: Literal["blocked"] = "blocked"
    database_used: Literal[False] = False
    provider_used: Literal[False] = False
    persistence_status: Literal["not_persisted"] = "not_persisted"
    authority: Literal["none"] = "none"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def preview_is_internally_consistent(self) -> PersonaPreview:
        expected_names = tuple(PersonaViewName)
        if tuple(view.name for view in self.views) != expected_names:
            raise ValueError("persona views must use canonical order")
        facets = tuple(facet for view in self.views for facet in view.facets)
        facets += self.scoped_objects
        if len(facets) != self.declaration_count:
            raise ValueError("declaration_count must match persona facets")
        if any(facet.subject_id != self.subject_id for facet in facets):
            raise ValueError("all persona facets must have one subject")
        if any(facet.data_class != self.data_class for facet in facets):
            raise ValueError("all persona facets must have one data class")
        expected_sources = tuple(sorted({facet.source_record_id for facet in facets}, key=str))
        if self.source_receipts != expected_sources:
            raise ValueError("source_receipts must exactly cover persona facets")
        expected_missing = tuple(view.name for view in self.views if not view.facets)
        if self.missing_views != expected_missing:
            raise ValueError("missing_views must match empty persona views")
        return self
