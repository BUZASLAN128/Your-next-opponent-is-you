from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.formal_decision import DecisionGroupKey
from ynoy.util import canonical_sha256

type Digest = str


class LocalAdoptionChallenge(StrictModel):
    """One short-lived, exact user-adoption operation awaiting a local signature."""

    protocol_version: Literal["local-adoption-challenge/0.1"] = "local-adoption-challenge/0.1"
    challenge_id: UUID
    actor_id: str = Field(min_length=1, max_length=256)
    subject_id: str = Field(min_length=1, max_length=256)
    review_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    claim_id: UUID
    claim_tuple_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    full_key: DecisionGroupKey
    expected_head: int = Field(ge=0)
    stream_id: str = Field(min_length=1, max_length=512)
    event_type: str = Field(min_length=1, max_length=128)
    payload_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    channel_id: Literal["local-openssh-passphrase/0.1"] = "local-openssh-passphrase/0.1"
    credential_fingerprint: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime
    data_class: Literal[DataClass.DERIVED_IDENTITY] = DataClass.DERIVED_IDENTITY
    challenge_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def challenge_is_canonical(self) -> LocalAdoptionChallenge:
        _require_trimmed(self.actor_id, self.subject_id, self.stream_id, self.event_type)
        if self.expires_at <= self.issued_at:
            raise ValueError("local adoption challenge expiry must follow issuance")
        _require_hash(self, "challenge_sha256")
        return self


class VerifiedLocalAdoption(StrictModel):
    """Receipt for a signature verified against one enrolled local public key."""

    protocol_version: Literal["verified-local-adoption/0.1"] = "verified-local-adoption/0.1"
    adoption_id: UUID
    challenge_id: UUID
    challenge_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    actor_id: str = Field(min_length=1, max_length=256)
    subject_id: str = Field(min_length=1, max_length=256)
    review_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    claim_id: UUID
    claim_tuple_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    full_key: DecisionGroupKey
    expected_head: int = Field(ge=0)
    stream_id: str = Field(min_length=1, max_length=512)
    event_type: str = Field(min_length=1, max_length=128)
    payload_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    channel_id: Literal["local-openssh-passphrase/0.1"] = "local-openssh-passphrase/0.1"
    credential_fingerprint: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    signature_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    verified_at: datetime
    data_class: Literal[DataClass.DERIVED_IDENTITY] = DataClass.DERIVED_IDENTITY
    receipt_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_canonical(self) -> VerifiedLocalAdoption:
        _require_trimmed(self.actor_id, self.subject_id, self.stream_id, self.event_type)
        _require_hash(self, "receipt_sha256")
        return self


class LocalAuthenticatorProfile(StrictModel):
    protocol_version: Literal["local-adoption-authenticator/0.1"] = (
        "local-adoption-authenticator/0.1"
    )
    actor_id: str = Field(min_length=1, max_length=256)
    public_key: str = Field(min_length=32, max_length=4096)
    credential_fingerprint: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    signature_namespace: Literal["ynoy-adoption"] = "ynoy-adoption"
    enrolled_at: datetime
    profile_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_is_canonical(self) -> LocalAuthenticatorProfile:
        _require_trimmed(self.actor_id, self.public_key)
        _require_hash(self, "profile_sha256")
        return self


def _require_trimmed(*values: str) -> None:
    if any(value != value.strip() for value in values):
        raise ValueError("local adoption identifiers must be trimmed")


def _require_hash(model: StrictModel, field: str) -> None:
    expected = canonical_sha256(model.model_dump(mode="json", exclude={field}))
    if getattr(model, field) != expected:
        raise ValueError(f"{field} does not match its canonical payload")
