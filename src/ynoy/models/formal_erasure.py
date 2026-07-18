from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.util import canonical_sha256

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ProducerKind(StrEnum):
    DATABASE_TABLE = "database_table"
    PRIVATE_ARTIFACT = "private_artifact"


class ErasureProducer(StrictModel):
    producer_id: str = Field(min_length=1)
    kind: ProducerKind
    handler_id: str = Field(min_length=1)


class ErasureRegistry(StrictModel):
    version: str = Field(min_length=1)
    producers: tuple[ErasureProducer, ...] = Field(min_length=1)
    handler_manifest_sha256: Sha256Digest
    registry_sha256: Sha256Digest

    @model_validator(mode="after")
    def registry_is_complete_and_canonical(self) -> ErasureRegistry:
        identifiers = tuple(item.producer_id for item in self.producers)
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("erasure producers must be sorted and unique")
        if any(
            value != value.strip()
            for value in (self.version, *(item.handler_id for item in self.producers))
        ):
            raise ValueError("erasure registry identifiers must be trimmed")
        _require_digest(self, "registry_sha256")
        return self


class ProducerUniverseAttestation(StrictModel):
    attestation_id: UUID
    attestor_id: str = Field(min_length=1)
    authority: Literal["independent"] = "independent"
    registry_version: str = Field(min_length=1)
    registry_sha256: Sha256Digest
    producer_ids: tuple[str, ...] = Field(min_length=1)
    handler_manifest_sha256: Sha256Digest
    issued_revision: int = Field(ge=0)
    valid_through_revision: int = Field(ge=0)
    attestation_sha256: Sha256Digest

    @model_validator(mode="after")
    def attestation_is_canonical(self) -> ProducerUniverseAttestation:
        if self.valid_through_revision < self.issued_revision:
            raise ValueError("attestation validity precedes its issue revision")
        if self.producer_ids != tuple(sorted(set(self.producer_ids))):
            raise ValueError("attested producer identifiers must be sorted and unique")
        _require_digest(self, "attestation_sha256")
        return self


class DeleteSuccess(StrictModel):
    status: Literal["local_database_deleted", "partial"]
    registry_sha256: Sha256Digest
    attestation_sha256: Sha256Digest | None = None
    contract_satisfied: bool = False
    universal_success: Literal[False] = False
    missing_proofs: tuple[str, ...]

    @model_validator(mode="after")
    def result_is_honest(self) -> DeleteSuccess:
        if self.contract_satisfied == bool(self.missing_proofs):
            raise ValueError("delete contract state contradicts missing proofs")
        return self


class ErasureTombstone(StrictModel):
    tombstone_id: UUID
    opaque_source_id: UUID
    registry_version: str = Field(min_length=1)
    deleted_at_revision: int = Field(ge=0)
    fence_active: Literal[True] = True


class ParameterInfluenceSurface(StrEnum):
    LABEL = "label"
    REWARD = "reward"
    SUMMARY = "summary"
    SELECTOR = "selector"
    HYPERPARAMETER = "hyperparameter"
    ADAPTER = "adapter"
    STEERING = "steering"


class ParameterInfluence(StrictModel):
    source_class: DataClass
    surface: ParameterInfluenceSurface
    transformed: bool = False


class ParameterUpdateDecision(StrictModel):
    performed: Literal[False] = False
    status: Literal["private_influence_prohibited", "not_implemented"]
    blocked_surfaces: tuple[ParameterInfluenceSurface, ...]


def _require_digest(model: StrictModel, field: str) -> None:
    payload = model.model_dump(mode="json", exclude={field})
    if getattr(model, field) != canonical_sha256(payload):
        raise ValueError(f"{field} does not match its canonical payload")
