from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.formal_decision import DecisionGroupKey
from ynoy.util import canonical_sha256

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AdoptionChallenge(StrictModel):
    challenge_id: UUID
    subject_id: str = Field(min_length=1)
    review_sha256: Sha256Digest
    claim_id: UUID
    claim_tuple_sha256: Sha256Digest
    full_key: DecisionGroupKey
    expected_head: int = Field(ge=0)
    channel_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    data_class: Literal[DataClass.PUBLIC_SYNTHETIC] = DataClass.PUBLIC_SYNTHETIC
    challenge_sha256: Sha256Digest

    @model_validator(mode="after")
    def challenge_is_canonical(self) -> AdoptionChallenge:
        _require_trimmed(self.subject_id, self.channel_id, self.verifier_version)
        _require_digest(self, "challenge_sha256")
        return self


class VerifiedAdoption(StrictModel):
    adoption_id: UUID
    challenge_id: UUID
    challenge_sha256: Sha256Digest
    subject_id: str = Field(min_length=1)
    review_sha256: Sha256Digest
    claim_id: UUID
    claim_tuple_sha256: Sha256Digest
    full_key: DecisionGroupKey
    expected_head: int = Field(ge=0)
    channel_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    response_sha256: Sha256Digest
    data_class: Literal[DataClass.PUBLIC_SYNTHETIC] = DataClass.PUBLIC_SYNTHETIC
    receipt_sha256: Sha256Digest

    @model_validator(mode="after")
    def receipt_is_canonical(self) -> VerifiedAdoption:
        _require_trimmed(self.subject_id, self.channel_id, self.verifier_version)
        _require_digest(self, "receipt_sha256")
        return self


class TrustedReviewAuthorization(StrictModel):
    actor_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_sha256: Sha256Digest
    stream_id: str = Field(min_length=1)
    allowed_event_types: tuple[str, ...] = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    authenticated: Literal[True] = True
    receipt_sha256: Sha256Digest

    @model_validator(mode="after")
    def authorization_is_canonical(self) -> TrustedReviewAuthorization:
        _require_trimmed(
            self.actor_id,
            self.subject_id,
            self.stream_id,
            self.policy_version,
            *self.allowed_event_types,
        )
        if len(set(self.allowed_event_types)) != len(self.allowed_event_types):
            raise ValueError("allowed review event types must be unique")
        _require_digest(self, "receipt_sha256")
        return self


class ReviewAppend(StrictModel):
    event_id: UUID
    stream_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    payload_sha256: Sha256Digest
    causation_id: UUID
    actor_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_sha256: Sha256Digest
    adoption_receipt_sha256: Sha256Digest
    policy_version: str = Field(min_length=1)
    authorization_receipt_sha256: Sha256Digest
    event_sha256: Sha256Digest

    @model_validator(mode="after")
    def event_is_canonical(self) -> ReviewAppend:
        _require_trimmed(
            self.stream_id,
            self.event_type,
            self.actor_id,
            self.subject_id,
            self.policy_version,
        )
        _require_digest(self, "event_sha256")
        return self


class ReviewAppendAck(StrictModel):
    event_id: UUID
    stream_id: str
    revision: int = Field(ge=1)
    event_sha256: Sha256Digest
    idempotent_replay: bool = False
    content: None = None


class AuthorizationQuery(StrictModel):
    actor_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    scope_id: str = Field(min_length=1)
    confirmation_id: str = Field(min_length=1)
    audit_context_id: str = Field(min_length=1)
    kill_switch_id: str = Field(min_length=1)
    request_sha256: Sha256Digest

    @model_validator(mode="after")
    def query_is_canonical(self) -> AuthorizationQuery:
        fields = (
            "actor_id",
            "subject_id",
            "capability",
            "scope_id",
            "confirmation_id",
            "audit_context_id",
            "kill_switch_id",
        )
        payload = {field: getattr(self, field) for field in fields}
        if self.request_sha256 != canonical_sha256(payload):
            raise ValueError("request_sha256 does not match its canonical payload")
        return self


class TrustedAuthorizationTuple(AuthorizationQuery):
    tuple_id: str = Field(min_length=1)
    enabled: Literal[True] = True
    receipt_sha256: Sha256Digest

    @model_validator(mode="after")
    def tuple_is_canonical(self) -> TrustedAuthorizationTuple:
        _require_digest(self, "receipt_sha256")
        return self


class AuthorizationDecision(StrictModel):
    allowed: bool
    reason: Literal["trusted_unique_match", "trusted_match_missing", "trusted_match_ambiguous"]
    tuple_id: str | None = None
    capability: str | None = None
    scope_id: str | None = None

    @model_validator(mode="after")
    def projection_matches_decision(self) -> AuthorizationDecision:
        projected = (self.tuple_id, self.capability, self.scope_id)
        if self.allowed != all(value is not None for value in projected):
            raise ValueError("authorization decision projection contradicts allow state")
        return self


class EgressLogicalEvent(StrictModel):
    target_class: str = Field(min_length=1)
    model_class: str = Field(min_length=1)
    payload_class: Literal[DataClass.PUBLIC_SYNTHETIC]
    payload_size_class: str = Field(min_length=1)
    allowed_header_classes: tuple[str, ...]
    call_sequence: int = Field(ge=1)
    retry_class: str = Field(min_length=1)
    error_class: str = Field(min_length=1)
    log_class: str = Field(min_length=1)
    telemetry_class: str = Field(min_length=1)


class EgressTrace(StrictModel):
    observer_id: str = Field(min_length=1)
    events: tuple[EgressLogicalEvent, ...]
    send_enabled: Literal[False] = False
    trace_sha256: Sha256Digest

    @model_validator(mode="after")
    def trace_is_canonical(self) -> EgressTrace:
        if self.observer_id != self.observer_id.strip():
            raise ValueError("observer identifier must be trimmed")
        if tuple(item.call_sequence for item in self.events) != tuple(
            range(1, len(self.events) + 1)
        ):
            raise ValueError("egress event sequence must be contiguous")
        _require_digest(self, "trace_sha256")
        return self


def _require_trimmed(*values: str) -> None:
    if any(value != value.strip() for value in values):
        raise ValueError("formal runtime identifiers must be trimmed")


def _require_digest(model: StrictModel, field: str) -> None:
    payload = model.model_dump(mode="json", exclude={field})
    if getattr(model, field) != canonical_sha256(payload):
        raise ValueError(f"{field} does not match its canonical payload")
