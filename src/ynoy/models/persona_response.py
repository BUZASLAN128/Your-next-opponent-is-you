from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.util import canonical_sha256

type Digest = str
type NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=8_192),
]
type ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]
type PersonaResponseArm = Literal["structured", "generic"]
type PersonaGenerationSource = Literal["local_model", "deterministic_runtime_guard"]

_JSON_OBJECT_ADAPTER = TypeAdapter(dict[str, Any])


class PersonaResponse(StrictModel):
    """A private, uncalibrated simulation with no decision or action authority."""

    protocol_version: Literal["persona-response/0.1"] = "persona-response/0.1"
    arm: PersonaResponseArm
    query_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    data_class: DataClass
    synthetic: bool
    expires_at: datetime
    response_text: NonEmptyText
    used_atom_ids: tuple[Digest, ...] = Field(max_length=64)
    evidence_receipts: tuple[Digest, ...] = Field(max_length=256)
    uncertainties: tuple[ShortText, ...] = Field(min_length=1, max_length=8)
    should_abstain: Literal[True] = True
    model: NonEmptyText
    revision: NonEmptyText
    artifact_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    generation_source: PersonaGenerationSource
    model_identity_status: Literal["locally_attested_not_endpoint_authenticated"] = (
        "locally_attested_not_endpoint_authenticated"
    )
    judgment_basis: Literal["abstention"] = "abstention"
    simulation_mode: Literal["structured_persona_candidate", "generic_control"]
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    authority: Literal["none"] = "none"
    action_status: Literal["not_performed"] = "not_performed"
    send_enabled: Literal[False] = False
    execute_enabled: Literal[False] = False
    automatic_core: Literal[False] = False
    persistent: Literal[False] = False
    retention_bound_to_pack: Literal[True] = True
    protected_holdout_used: Literal[False] = False
    target_object_accepted: Literal[False] = False
    target_seen: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    provenance_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def response_is_canonical(self) -> PersonaResponse:
        if self.used_atom_ids != tuple(sorted(set(self.used_atom_ids))):
            raise ValueError("persona response atom identifiers must be sorted and unique")
        if self.evidence_receipts != tuple(sorted(set(self.evidence_receipts))):
            raise ValueError("persona response evidence receipts must be sorted and unique")
        if self.arm == "generic" and self.used_atom_ids:
            raise ValueError("generic response cannot cite persona atoms")
        if self.generation_source == "deterministic_runtime_guard" and self.used_atom_ids:
            raise ValueError("deterministic runtime guard cannot cite persona atoms")
        expected_class = (
            DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.DERIVED_IDENTITY
        )
        if self.data_class != expected_class:
            raise ValueError("persona response data class contradicts its pack mode")
        if self.simulation_mode != _simulation_mode(self.arm):
            raise ValueError("persona response simulation mode contradicts its arm")
        if self.provenance_sha256 != canonical_sha256(_provenance_payload(self)):
            raise ValueError("persona response provenance hash does not match")
        payload = self.model_dump(mode="json", exclude={"response_sha256"})
        if self.response_sha256 != canonical_sha256(payload):
            raise ValueError("persona response hash does not match")
        return self


def response_hashes(payload: dict[str, object]) -> tuple[Digest, Digest]:
    normalized = _JSON_OBJECT_ADAPTER.dump_python(payload, mode="json")
    provenance = canonical_sha256(
        {
            key: normalized[key]
            for key in (
                "arm",
                "query_sha256",
                "pack_id",
                "pack_sha256",
                "source_manifest_sha256",
                "source_head_sha256",
                "source_head_revision",
                "data_class",
                "synthetic",
                "expires_at",
                "used_atom_ids",
                "evidence_receipts",
                "model",
                "revision",
                "artifact_sha256",
                "generation_source",
            )
        }
    )
    response = canonical_sha256({**normalized, "provenance_sha256": provenance})
    return provenance, response


def _provenance_payload(response: PersonaResponse) -> dict[str, object]:
    keys = {
        "arm",
        "query_sha256",
        "pack_id",
        "pack_sha256",
        "source_manifest_sha256",
        "source_head_sha256",
        "source_head_revision",
        "data_class",
        "synthetic",
        "expires_at",
        "used_atom_ids",
        "evidence_receipts",
        "model",
        "revision",
        "artifact_sha256",
        "generation_source",
    }
    return response.model_dump(mode="json", include=keys)


def _simulation_mode(arm: PersonaResponseArm) -> str:
    return "structured_persona_candidate" if arm == "structured" else "generic_control"
