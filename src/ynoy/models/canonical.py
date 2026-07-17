from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
from ynoy.models.base import (
    CandidateKind,
    CandidateStatus,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    RecordBase,
    ScopeRef,
    SourceAuthority,
    Speaker,
    StrictModel,
)
from ynoy.models.review_vocab import AtomicClaimType, ReviewAction, TargetLayer
from ynoy.util import canonical_sha256

type Sha256Digest = str


class PersonaStratum(StrEnum):
    DECISIONS_AND_POLICY = "decisions_preferences_scoped_policy"
    VALUES_AND_BELIEFS = "values_and_beliefs"
    GOALS_AND_CONTINUITY = "goals_mission_and_continuity"
    COMMUNICATION_AND_METACOGNITION = "communication_behavior_and_metacognition"
    SKILLS_NARRATIVE_AND_RELATIONSHIPS = "skills_narrative_and_relationships"


class CanonicalClaim(RecordBase):
    subject_id: str = Field(min_length=1)
    claim_holder: Literal[ClaimHolder.REPRESENTED_USER] = ClaimHolder.REPRESENTED_USER
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    explicit_user_adoption: Literal[True] = True
    claim_type: AtomicClaimType
    target_layer: TargetLayer
    literal_statement: str = Field(min_length=1)
    interpretation: str | None = None
    candidate_consequence: str | None = None
    persona_kind: CandidateKind | None = None
    persona_stratum: PersonaStratum | None = None
    scope: ScopeRef
    decision_label: DecisionLabel | None = None
    status: CandidateStatus = CandidateStatus.CONFIRMED
    data_class: DataClass
    synthetic: bool
    admission_receipt_id: UUID
    source_link_ids: tuple[UUID, ...] = Field(min_length=1)
    supersedes_claim_id: UUID | None = None
    superseded_by: UUID | None = None
    claim_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def canonical_contract_is_consistent(self) -> CanonicalClaim:
        _require_claim_identity(self)
        _require_claim_layer(self)
        _require_claim_lifecycle(self)
        if self.claim_sha256 != canonical_claim_digest(self):
            raise ValueError("canonical claim hash does not match its payload")
        return self

    @property
    def retrieval_text(self) -> str:
        return self.interpretation or self.literal_statement


class ClaimSourceLink(RecordBase):
    claim_id: UUID
    source_receipt_id: UUID
    subject_id: str = Field(min_length=1)
    source_data_class: DataClass
    source_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    character_start: int = Field(ge=0)
    character_end: int = Field(ge=1)
    span_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    origin_cluster_id: str = Field(min_length=1)
    link_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def source_link_is_consistent(self) -> ClaimSourceLink:
        if self.subject_id != self.subject_id.strip():
            raise ValueError("source link subject must be trimmed")
        if self.source_data_class not in {DataClass.PUBLIC_SYNTHETIC, DataClass.RAW_CORPUS}:
            raise ValueError("source link must reference D0 or D2 evidence")
        if self.character_end <= self.character_start:
            raise ValueError("source link interval must be non-empty")
        if self.link_sha256 != canonical_sha256(
            self.model_dump(mode="json", exclude={"link_sha256"})
        ):
            raise ValueError("source link hash does not match its payload")
        return self


class ClaimAdmissionReceipt(RecordBase):
    claim_id: UUID
    subject_id: str = Field(min_length=1)
    actor: Literal[Speaker.USER] = Speaker.USER
    claim_holder: Literal[ClaimHolder.REPRESENTED_USER] = ClaimHolder.REPRESENTED_USER
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    explicit_adoption: Literal[True] = True
    adoption_action: ReviewAction
    adoption_receipt_id: UUID
    adoption_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_link_ids: tuple[UUID, ...] = Field(min_length=1)
    source_count: int = Field(ge=1)
    data_class: DataClass
    supersedes_claim_id: UUID | None = None
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: Literal["none"] = "none"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def admission_receipt_is_consistent(self) -> ClaimAdmissionReceipt:
        if self.subject_id != self.subject_id.strip():
            raise ValueError("admission receipt subject must be trimmed")
        if self.source_count != len(self.source_link_ids):
            raise ValueError("admission source count must match source links")
        if self.data_class not in {DataClass.PUBLIC_SYNTHETIC, DataClass.DERIVED_IDENTITY}:
            raise ValueError("admission receipt must use D0 or D3")
        if self.adoption_action in {
            ReviewAction.REJECT,
            ReviewAction.PROPOSE_FOR_CORE,
        }:
            raise ValueError("non-adopting review action cannot create an admission receipt")
        if self.receipt_sha256 != canonical_sha256(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("admission receipt hash does not match its payload")
        return self


class CanonicalClaimAdmission(StrictModel):
    claim: CanonicalClaim
    receipt: ClaimAdmissionReceipt
    source_links: tuple[ClaimSourceLink, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def bundle_is_consistent(self) -> CanonicalClaimAdmission:
        link_ids = tuple(item.record_id for item in self.source_links)
        if self.claim.admission_receipt_id != self.receipt.record_id:
            raise ValueError("claim must reference its admission receipt")
        if self.claim.record_id != self.receipt.claim_id:
            raise ValueError("admission receipt must reference its claim")
        if self.claim.claim_sha256 != self.receipt.claim_sha256:
            raise ValueError("admission receipt must bind the canonical claim hash")
        if self.claim.source_link_ids != link_ids or self.receipt.source_link_ids != link_ids:
            raise ValueError("claim, receipt, and source links must share one ordered link set")
        if any(
            item.claim_id != self.claim.record_id or item.subject_id != self.claim.subject_id
            for item in self.source_links
        ):
            raise ValueError("source links must belong to the admitted claim and subject")
        if self.receipt.subject_id != self.claim.subject_id:
            raise ValueError("admission receipt subject must match claim")
        if self.receipt.data_class != self.claim.data_class:
            raise ValueError("admission receipt data class must match claim")
        if self.receipt.supersedes_claim_id != self.claim.supersedes_claim_id:
            raise ValueError("admission supersession references must match")
        return self


def _bounded(value: str | None) -> bool:
    return value is None or (
        bool(value.strip())
        and value == value.strip()
        and len(value.encode("utf-8")) <= DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
    )


def canonical_claim_digest(claim: CanonicalClaim) -> str:
    """Hash immutable claim meaning while lifecycle projection remains updateable."""
    return canonical_sha256(
        claim.model_dump(
            mode="json",
            exclude={"claim_sha256", "status", "superseded_by"},
        )
    )


def _require_claim_identity(claim: CanonicalClaim) -> None:
    if claim.subject_id != claim.subject_id.strip() or claim.scope.person_id != claim.subject_id:
        raise ValueError("canonical claim subject must be trimmed and match scope")
    if not all(
        _bounded(value)
        for value in (claim.literal_statement, claim.interpretation, claim.candidate_consequence)
    ):
        raise ValueError("canonical claim text must be trimmed and bounded")
    expected = DataClass.PUBLIC_SYNTHETIC if claim.synthetic else DataClass.DERIVED_IDENTITY
    if claim.data_class != expected:
        raise ValueError("canonical claim data class must match synthetic state")
    if len(set(claim.source_link_ids)) != len(claim.source_link_ids):
        raise ValueError("canonical claim source links must be unique")


def _require_claim_layer(claim: CanonicalClaim) -> None:
    is_persona = claim.target_layer == TargetLayer.PERSONA_CANDIDATE
    has_persona_fields = claim.persona_kind is not None and claim.persona_stratum is not None
    if is_persona != has_persona_fields:
        raise ValueError("persona claims alone require persona kind and stratum")


def _require_claim_lifecycle(claim: CanonicalClaim) -> None:
    if claim.status not in {
        CandidateStatus.CONFIRMED,
        CandidateStatus.SUPERSEDED,
        CandidateStatus.INVALIDATED,
    }:
        raise ValueError("canonical claims cannot use proposal or dispute states")
    if claim.supersedes_claim_id == claim.record_id or claim.superseded_by == claim.record_id:
        raise ValueError("canonical claim cannot supersede itself")
    if claim.status == CandidateStatus.SUPERSEDED and claim.superseded_by is None:
        raise ValueError("superseded canonical claim requires its replacement")
    if claim.status == CandidateStatus.CONFIRMED and claim.superseded_by is not None:
        raise ValueError("active canonical claim cannot already have a replacement")
