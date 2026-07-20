from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.full_persona_pack import PersonaLayer
from ynoy.models.persona_adjudication import (
    PersonaAdjudicationProfile,
    pattern_recommendation_disposition,
)
from ynoy.models.persona_dossier import PersonaDossier
from ynoy.models.persona_evolution import PersonaEvolutionProfile
from ynoy.util import canonical_sha256

type Digest = str
type PersonaPackageProtocol = Literal["full-persona-package/0.2", "full-persona-package/0.3"]


class PersonaLayerSummary(StrictModel):
    layer: PersonaLayer
    retained_atom_count: int = Field(ge=0)
    unique_semantic_claim_count: int = Field(ge=0)
    represented_observation_count: int = Field(ge=0)
    duplicate_observation_count: int = Field(ge=0)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> PersonaLayerSummary:
        if self.unique_semantic_claim_count > self.retained_atom_count:
            raise ValueError("persona package semantic claim count is inconsistent")
        if self.duplicate_observation_count > self.represented_observation_count:
            raise ValueError("persona package duplicate count is inconsistent")
        return self


class PersonaPackageInspection(StrictModel):
    protocol_version: PersonaPackageProtocol
    package_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    package_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    adjudication_status: Literal["absent", "present"]
    review_eligible: bool

    @model_validator(mode="after")
    def inspection_is_consistent(self) -> PersonaPackageInspection:
        expected = self.protocol_version == "full-persona-package/0.3"
        if self.review_eligible != expected:
            raise ValueError("persona package review eligibility contradicts its protocol")
        expected_status = "present" if expected else "absent"
        if self.adjudication_status != expected_status:
            raise ValueError("persona package adjudication status contradicts its protocol")
        return self


class FullPersonaPackage(StrictModel):
    """Persistent private package over a complete scan and bounded retained projection."""

    protocol_version: Literal["full-persona-package/0.3"] = "full-persona-package/0.3"
    package_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    pack_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    expires_at: datetime
    data_class: DataClass
    synthetic: bool
    processed_evidence_count: int = Field(ge=0)
    retained_atom_count: int = Field(ge=0)
    unique_semantic_claim_count: int = Field(ge=0)
    layer_summaries: tuple[PersonaLayerSummary, ...] = Field(min_length=12, max_length=12)
    dossier: PersonaDossier
    evolution: PersonaEvolutionProfile
    adjudication: PersonaAdjudicationProfile
    source_scan_status: Literal["complete_verified"] = "complete_verified"
    history_scope: Literal["all_retained_pack_history"] = "all_retained_pack_history"
    retained_projection_exhaustive: Literal[False] = False
    identity_fact_policy: Literal["literal_evidence_or_unknown"] = "literal_evidence_or_unknown"
    model_enrichment: Literal["not_used"] = "not_used"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    semantic_adoption: Literal["not_established"] = "not_established"
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    authority: Literal["none"] = "none"
    persistent: Literal[True] = True
    package_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def package_is_canonical(self) -> FullPersonaPackage:
        if tuple(item.layer for item in self.layer_summaries) != tuple(PersonaLayer):
            raise ValueError("persona package layer order changed")
        if sum(item.retained_atom_count for item in self.layer_summaries) != (
            self.retained_atom_count
        ):
            raise ValueError("persona package retained atom count is inconsistent")
        if sum(item.unique_semantic_claim_count for item in self.layer_summaries) != (
            self.unique_semantic_claim_count
        ):
            raise ValueError("persona package semantic claim count is inconsistent")
        if not _projections_match(self):
            raise ValueError("persona package projections do not match their source pack")
        expected_id = canonical_sha256(
            {
                "protocol_version": self.protocol_version,
                "pack_sha256": self.pack_sha256,
                "dossier_sha256": self.dossier.dossier_sha256,
                "evolution_sha256": self.evolution.evolution_sha256,
                "adjudication_sha256": self.adjudication.adjudication_sha256,
            }
        )
        if self.package_id != expected_id:
            raise ValueError("persona package identifier is invalid")
        payload = self.model_dump(mode="json", exclude={"package_sha256"})
        if self.package_sha256 != canonical_sha256(payload):
            raise ValueError("persona package hash does not match")
        return self


def _projections_match(package: FullPersonaPackage) -> bool:
    dossier = package.dossier
    expected_class = DataClass.PUBLIC_SYNTHETIC if package.synthetic else DataClass.DERIVED_IDENTITY
    return bool(
        package.data_class == expected_class
        and dossier.pack_id == package.pack_id
        and dossier.pack_sha256 == package.pack_sha256
        and dossier.source_run_id == package.source_run_id
        and dossier.source_head_sha256 == package.source_head_sha256
        and dossier.source_head_revision == package.source_head_revision
        and dossier.expires_at == package.expires_at
        and dossier.data_class == package.data_class
        and dossier.synthetic == package.synthetic
        and dossier.processed_evidence_count == package.processed_evidence_count
        and dossier.retained_atom_count == package.retained_atom_count
        and package.evolution.pack_id == package.pack_id
        and package.evolution.pack_sha256 == package.pack_sha256
        and package.adjudication.pack_id == package.pack_id
        and package.adjudication.pack_sha256 == package.pack_sha256
        and package.adjudication.evolution_sha256 == package.evolution.evolution_sha256
        and package.adjudication.source_pattern_candidate_count
        == package.evolution.total_pattern_candidate_count
        and package.adjudication.source_transition_candidate_count
        == package.evolution.total_transition_candidate_count
        and len(package.adjudication.recommendations)
        == len(package.evolution.patterns) + len(package.evolution.transitions)
        and _adjudication_targets_match(package)
    )


def _adjudication_targets_match(package: FullPersonaPackage) -> bool:
    expected: dict[tuple[str, str], tuple[str, str, int]] = {}
    for item in package.evolution.patterns:
        key = (
            "pattern",
            canonical_sha256({"kind": "pattern", "candidate": item.model_dump(mode="json")}),
        )
        action, rationale = pattern_recommendation_disposition(item.evidence_strength)
        expected[key] = (action, rationale, item.evidence_count)
    for transition in package.evolution.transitions:
        key = (
            "transition",
            canonical_sha256(
                {"kind": "transition", "candidate": transition.model_dump(mode="json")}
            ),
        )
        expected[key] = ("defer_scope_required", "contextual_transition_scope_unknown", 2)
    actual = {
        (item.target_kind, item.target_id): (item.action, item.rationale, item.evidence_count)
        for item in package.adjudication.recommendations
    }
    return actual == expected
