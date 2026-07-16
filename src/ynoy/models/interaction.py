from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
from ynoy.models.base import (
    ClaimHolder,
    DataClass,
    RecordBase,
    ScopeRef,
    SourceAuthority,
    Speaker,
    StrictModel,
)
from ynoy.models.review_vocab import (
    AtomicClaimType,
    ClaimModality,
    ConfidenceLevel,
    NullReason,
    ReviewAction,
    SpeechAct,
    TargetLayer,
)
from ynoy.util import sha256_text


def _is_bounded_text(value: str) -> bool:
    return (
        bool(value.strip()) and len(value.encode("utf-8")) <= DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
    )


class NullableReviewText(StrictModel):
    value: str | None = None
    null_reason: NullReason | None = None
    authority_to_fill: Literal["user_only", "evidence_required"]

    @model_validator(mode="after")
    def value_or_reason(self) -> NullableReviewText:
        if self.value is None:
            if self.null_reason is None:
                raise ValueError("missing review text requires an explicit null reason")
        elif self.null_reason is not None or not _is_bounded_text(self.value):
            raise ValueError("review text must be bounded and cannot also have a null reason")
        return self


class InteractionPrompt(StrictModel):
    source_locator: str = Field(min_length=1)
    speaker: Speaker
    text: NullableReviewText
    content_sha256: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def hash_matches_available_text(self) -> InteractionPrompt:
        if self.source_locator != self.source_locator.strip():
            raise ValueError("prompt source locator must be trimmed")
        if self.text.value is None:
            if self.content_sha256 is not None:
                raise ValueError("unavailable prompt text cannot have a content hash")
        elif self.content_sha256 != sha256_text(self.text.value):
            raise ValueError("prompt content hash does not match exact text")
        return self


class InteractionReceipt(RecordBase):
    """Exact user-response evidence for one non-persisting review operation."""

    source_name: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    event_time: datetime | None = None
    event_time_precision: Literal["exact", "date_only", "unknown"]
    integrity_status: Literal["provisional_unsealed"] = "provisional_unsealed"
    prompt: InteractionPrompt
    response: str = Field(min_length=1)
    response_sha256: str = Field(min_length=64, max_length=64)
    speaker: Literal[Speaker.USER] = Speaker.USER
    claim_holder: Literal[ClaimHolder.REPRESENTED_USER] = ClaimHolder.REPRESENTED_USER
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    authorship: Literal["direct_user_authored"] = "direct_user_authored"
    adoption_status: Literal["source_statement_only"] = "source_statement_only"
    contains_quoted_content: Literal[False] = False
    subject_id: str = Field(min_length=1)
    scope: ScopeRef
    question_resolved: NullableReviewText
    source_data_class: DataClass
    synthetic: bool

    @model_validator(mode="after")
    def source_contract_is_consistent(self) -> InteractionReceipt:
        identifiers = (self.source_name, self.conversation_id, self.turn_id)
        if any(not value.strip() or value != value.strip() for value in identifiers):
            raise ValueError("interaction source identifiers must be trimmed")
        if self.subject_id != self.subject_id.strip() or self.scope.person_id != self.subject_id:
            raise ValueError("interaction subject must be trimmed and match scope person")
        if self.event_time_precision == "unknown":
            if self.event_time is not None:
                raise ValueError("unknown event time cannot carry a timestamp")
        elif self.event_time is None:
            raise ValueError("known event time precision requires a timestamp")
        elif self.event_time_precision == "date_only" and any(
            (self.event_time.hour, self.event_time.minute, self.event_time.second)
        ):
            raise ValueError("date-only event time must use midnight")
        if not _is_bounded_text(self.response):
            raise ValueError("interaction response must be non-empty and bounded")
        if self.response_sha256 != sha256_text(self.response):
            raise ValueError("response content hash does not match exact text")
        expected_class = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.source_data_class != expected_class:
            raise ValueError("interaction source data class does not match synthetic state")
        return self


class SourceSpan(StrictModel):
    character_start: int = Field(ge=0)
    character_end: int = Field(ge=1)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def interval_is_valid(self) -> SourceSpan:
        if self.character_end <= self.character_start or not _is_bounded_text(self.text):
            raise ValueError("source span must be a non-empty bounded character interval")
        return self


class ConfidenceDimensions(StrictModel):
    attribution: Literal[ConfidenceLevel.HIGH] = ConfidenceLevel.HIGH
    classification: ConfidenceLevel
    applicability: ConfidenceLevel


class AtomicClaimProposal(RecordBase):
    """One proposed interpretation linked to exact spans in one receipt."""

    receipt_id: UUID
    subject_id: str = Field(min_length=1)
    source_spans: tuple[SourceSpan, ...] = Field(min_length=1)
    literal_normalization: str = Field(min_length=1)
    inference: NullableReviewText
    candidate_consequence: NullableReviewText
    speech_act: SpeechAct
    modality: ClaimModality
    claim_type: AtomicClaimType
    target_layer: TargetLayer
    scope: ScopeRef
    confidence: ConfidenceDimensions
    epistemic_status: Literal["observed_source_proposed_interpretation"] = (
        "observed_source_proposed_interpretation"
    )
    status: Literal["proposed"] = "proposed"
    confirmation_required: Literal[True] = True
    core_eligible: Literal[False] = False

    @model_validator(mode="after")
    def proposal_contract_is_consistent(self) -> AtomicClaimProposal:
        if self.subject_id != self.subject_id.strip() or self.scope.person_id != self.subject_id:
            raise ValueError("atomic claim subject must be trimmed and match scope person")
        if (
            not _is_bounded_text(self.literal_normalization)
            or self.literal_normalization != self.literal_normalization.strip()
        ):
            raise ValueError("literal normalization must be non-empty and bounded")
        return self


class ReviewProviderEvidence(StrictModel):
    """Pinned local-model identity for one proposal-only review operation."""

    endpoint_kind: Literal["loopback_openai_compatible"] = "loopback_openai_compatible"
    model: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_attested: Literal[True] = True

    @model_validator(mode="after")
    def identifiers_are_canonical(self) -> ReviewProviderEvidence:
        if self.model != self.model.strip() or self.revision != self.revision.strip():
            raise ValueError("review provider identifiers must be trimmed")
        return self


class InteractionReview(StrictModel):
    """A local review projection with no persistence, authority, or promotion."""

    status: Literal["review"] = "review"
    review_status: Literal["awaiting_user_confirmation"] = "awaiting_user_confirmation"
    source: InteractionReceipt
    subject_id: str
    source_data_class: DataClass
    review_data_class: DataClass
    claims: tuple[AtomicClaimProposal, ...] = Field(min_length=1)
    claim_count: int = Field(ge=1)
    allowed_actions: tuple[ReviewAction, ...] = Field(min_length=1)
    unknowns: tuple[str, ...] = Field(min_length=1)
    database_used: Literal[False] = False
    proposal_method: Literal["manual", "local_model"] = "manual"
    provider_evidence: ReviewProviderEvidence | None = None
    provider_used: bool = False
    persistence_status: Literal["not_persisted"] = "not_persisted"
    authority: Literal["none"] = "none"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def review_contract_is_consistent(self) -> InteractionReview:
        expected_class = (
            DataClass.PUBLIC_SYNTHETIC if self.source.synthetic else DataClass.DERIVED_IDENTITY
        )
        if self.subject_id != self.source.subject_id:
            raise ValueError("review subject must match interaction source")
        if self.source_data_class != self.source.source_data_class:
            raise ValueError("review source data class must match interaction source")
        if self.review_data_class != expected_class:
            raise ValueError("review data class must match source sensitivity")
        if self.claim_count != len(self.claims):
            raise ValueError("review claim count must match claims")
        if len({claim.record_id for claim in self.claims}) != len(self.claims):
            raise ValueError("review claims must have unique identifiers")
        if any(
            claim.receipt_id != self.source.record_id or claim.subject_id != self.subject_id
            for claim in self.claims
        ):
            raise ValueError("review claims must match source receipt and subject")
        if self.allowed_actions != tuple(ReviewAction):
            raise ValueError("review must expose every canonical correction action")
        model_assisted = self.proposal_method == "local_model"
        if self.provider_used != model_assisted:
            raise ValueError("review provider flag must match proposal method")
        if (self.provider_evidence is not None) != model_assisted:
            raise ValueError("model-assisted review requires pinned provider evidence")
        return self
