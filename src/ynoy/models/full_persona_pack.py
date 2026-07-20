from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.full_persona import EvidenceRole
from ynoy.util import canonical_sha256, sha256_text

type Digest = str


class PersonaLayer(StrEnum):
    TIMELINE = "timeline"
    AUTOBIOGRAPHY = "autobiography"
    VALUES = "values"
    GOALS = "goals"
    DECISIONS = "decisions"
    EVIDENCE = "evidence"
    RISK = "risk"
    KNOWLEDGE = "knowledge"
    SKILLS = "skills"
    RELATIONSHIPS = "relationships"
    CONTRADICTIONS = "contradictions"
    RESPONSE_POLICY = "response_policy"


class PersonaEvidenceBasis(StrEnum):
    LITERAL = "literal"
    MODEL_INFERENCE = "model_inference"
    UNKNOWN = "unknown"


class PersonaAtomStatus(StrEnum):
    OBSERVED = "observed"
    PENDING = "pending"
    CONFLICTED = "conflicted"
    UNKNOWN = "unknown"


class PersonaPackBuildConfig(StrictModel):
    schema_version: Literal["persona-pack-build/0.3"] = "persona-pack-build/0.3"
    identity_rules_version: Literal["identity-rules/0.3"] = "identity-rules/0.3"
    max_atoms_per_layer: int = Field(default=128, ge=4, le=1_024)
    max_excerpt_chars: int = Field(default=2_048, ge=128, le=8_192)
    max_retrieval_hits: int = Field(default=12, ge=1, le=64)

    @property
    def config_sha256(self) -> Digest:
        return canonical_sha256(self.model_dump(mode="json"))


class PersonaSupportRef(StrictModel):
    evidence_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    byte_start: int = Field(ge=0)
    byte_length: int = Field(ge=1)
    line_number: int = Field(ge=1)
    event_time: datetime
    time_basis: Literal["event", "session_start"]
    evidence_role: EvidenceRole
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    excerpt: str = Field(min_length=1, max_length=8_192)
    excerpt_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    support_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def support_is_canonical(self) -> PersonaSupportRef:
        if self.char_end - self.char_start != len(self.excerpt):
            raise ValueError("persona support character span does not match its excerpt")
        if self.excerpt_sha256 != sha256_text(self.excerpt):
            raise ValueError("persona support excerpt hash does not match")
        payload = self.model_dump(mode="json", exclude={"support_sha256"})
        if self.support_sha256 != canonical_sha256(payload):
            raise ValueError("persona support receipt hash does not match")
        return self


class PersonaAtom(StrictModel):
    atom_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    layer: PersonaLayer
    semantic_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    claim: str = Field(min_length=1, max_length=8_192)
    basis: PersonaEvidenceBasis
    status: PersonaAtomStatus
    source_role: EvidenceRole | None = None
    support: tuple[PersonaSupportRef, ...] = ()
    evidence_ids: tuple[Digest, ...] = ()
    evidence_receipts: tuple[Digest, ...] = ()
    observation_count: int = Field(default=1, ge=0)
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    adopted: Literal[False] = False
    semantic_adoption: Literal["not_established"] = "not_established"
    core_eligible: Literal[False] = False
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def atom_is_canonical(self) -> PersonaAtom:
        evidence_ids = tuple(item.evidence_id for item in self.support)
        receipts = tuple(item.support_sha256 for item in self.support)
        if self.evidence_ids != evidence_ids or self.evidence_receipts != receipts:
            raise ValueError("persona atom evidence inventory does not match its support")
        if self.basis == PersonaEvidenceBasis.UNKNOWN and self.support:
            raise ValueError("unknown persona atoms cannot claim evidence support")
        if self.basis != PersonaEvidenceBasis.UNKNOWN and not self.support:
            raise ValueError("supported persona atoms require evidence receipts")
        if self.support and (
            self.first_observed_at is None
            or self.last_observed_at is None
            or self.first_observed_at > self.last_observed_at
        ):
            raise ValueError("persona atom observation interval is invalid")
        payload = self.model_dump(mode="json", exclude={"atom_id"})
        if self.atom_id != canonical_sha256(payload):
            raise ValueError("persona atom hash does not match")
        return self


class PersonaLayerView(StrictModel):
    layer: PersonaLayer
    atoms: tuple[PersonaAtom, ...] = ()
    unknowns: tuple[str, ...] = ()

    @model_validator(mode="after")
    def layer_is_canonical(self) -> PersonaLayerView:
        if any(atom.layer != self.layer for atom in self.atoms):
            raise ValueError("persona layer contains an atom from another layer")
        ids = tuple(atom.atom_id for atom in self.atoms)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("persona layer atoms must be sorted and unique")
        if len(set(self.unknowns)) != len(self.unknowns):
            raise ValueError("persona layer unknowns must be unique")
        return self


class PersonaPack(StrictModel):
    protocol_version: Literal["persona-pack/0.2"] = "persona-pack/0.2"
    pack_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    expires_at: datetime
    config: PersonaPackBuildConfig
    data_class: DataClass
    synthetic: bool
    processed_evidence_count: int = Field(ge=0)
    retained_atom_count: int = Field(ge=0)
    layers: tuple[PersonaLayerView, ...] = Field(min_length=12, max_length=12)
    unknowns: tuple[str, ...]
    model_enrichment: Literal["not_used"] = "not_used"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    authority: Literal["none"] = "none"
    pack_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def run_id(self) -> Digest:
        return self.source_run_id

    @model_validator(mode="after")
    def pack_is_canonical(self) -> PersonaPack:
        if tuple(view.layer for view in self.layers) != tuple(PersonaLayer):
            raise ValueError("persona pack must preserve the canonical twelve-layer order")
        count = sum(len(view.atoms) for view in self.layers)
        if self.retained_atom_count != count:
            raise ValueError("persona pack atom count does not reconcile")
        expected_class = (
            DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.DERIVED_IDENTITY
        )
        if self.data_class != expected_class:
            raise ValueError("persona pack data class contradicts its mode")
        expected_id = canonical_sha256(
            {
                "source_run_id": self.source_run_id,
                "source_head_sha256": self.source_head_sha256,
                "config_sha256": self.config.config_sha256,
            }
        )
        if self.pack_id != expected_id:
            raise ValueError("persona pack identifier does not bind its source head")
        payload = self.model_dump(mode="json", exclude={"pack_sha256"})
        if self.pack_sha256 != canonical_sha256(payload):
            raise ValueError("persona pack hash does not match")
        return self


class PersonaPackReceipt(StrictModel):
    pack_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    relative_path: str = Field(pattern=r"^[0-9a-f]{64}/[0-9a-f]{64}\.json$")
    receipt_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_canonical(self) -> PersonaPackReceipt:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("persona pack receipt hash does not match")
        return self


class PersonaRetrievalHit(StrictModel):
    atom_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    layer: PersonaLayer
    claim: str
    score: int = Field(ge=1)
    evidence_receipts: tuple[Digest, ...] = Field(min_length=1)
