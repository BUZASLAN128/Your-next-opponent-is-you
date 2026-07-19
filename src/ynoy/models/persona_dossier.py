from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.full_persona_pack import PersonaLayer
from ynoy.util import canonical_sha256

type Digest = str
type DossierTopicKey = Literal[
    "birth",
    "childhood",
    "education",
    "exams",
    "work_projects",
    "knowledge",
    "skills",
    "values",
    "goals",
    "decision_behavior",
    "risk_boundaries",
    "relationships",
    "contradictions",
    "response_style",
]
type CandidateText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_200)
]
type UnknownCode = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=128)
]

DOSSIER_TOPIC_ORDER: tuple[DossierTopicKey, ...] = (
    "birth",
    "childhood",
    "education",
    "exams",
    "work_projects",
    "knowledge",
    "skills",
    "values",
    "goals",
    "decision_behavior",
    "risk_boundaries",
    "relationships",
    "contradictions",
    "response_style",
)


class PersonaDossierCandidate(StrictModel):
    atom_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    layer: PersonaLayer
    claim: CandidateText
    truth_status: Literal["observed", "observed_unadopted", "conflicted_observation"]
    source_role: Literal["direct_user_expression"] = "direct_user_expression"
    evidence_receipts: tuple[Digest, ...] = Field(min_length=1, max_length=4)
    evidence_receipt_count: int = Field(ge=1)
    first_observed_at: datetime
    last_observed_at: datetime
    adopted: Literal[False] = False
    semantic_adoption: Literal["not_established"] = "not_established"
    core_eligible: Literal[False] = False
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def candidate_is_consistent(self) -> PersonaDossierCandidate:
        if self.first_observed_at > self.last_observed_at:
            raise ValueError("persona dossier observation interval is invalid")
        if self.evidence_receipts != tuple(sorted(set(self.evidence_receipts))):
            raise ValueError("persona dossier receipts must be sorted and unique")
        if self.evidence_receipt_count < len(self.evidence_receipts):
            raise ValueError("persona dossier receipt count is inconsistent")
        return self


class PersonaDossierStyleSupport(StrictModel):
    atom_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_receipts: tuple[Digest, ...] = Field(min_length=1, max_length=1)


class PersonaDossierStyleSignal(StrictModel):
    name: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    guidance: str = Field(min_length=1, max_length=256)
    supports: tuple[PersonaDossierStyleSupport, ...] = Field(min_length=2, max_length=2)
    status: Literal["derived_unadopted"] = "derived_unadopted"
    authority: Literal["none"] = "none"


class PersonaDossierTopic(StrictModel):
    key: DossierTopicKey
    evidence_state: Literal[
        "literal_candidates", "conflicted_candidates", "derived_unadopted", "unknown"
    ]
    total_candidate_count: int = Field(ge=0)
    candidates: tuple[PersonaDossierCandidate, ...] = Field(max_length=8)
    style_signals: tuple[PersonaDossierStyleSignal, ...] = Field(max_length=8)
    unknowns: tuple[UnknownCode, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def topic_is_consistent(self) -> PersonaDossierTopic:
        if self.total_candidate_count < len(self.candidates):
            raise ValueError("persona dossier candidate count is inconsistent")
        if self.key == "response_style":
            if self.candidates or self.total_candidate_count:
                raise ValueError("response style cannot contain literal dossier candidates")
            expected = "derived_unadopted" if self.style_signals else "unknown"
        else:
            if self.style_signals:
                raise ValueError("only response style can contain derived style signals")
            expected = _candidate_state(self.candidates)
        if self.evidence_state != expected:
            raise ValueError("persona dossier evidence state is inconsistent")
        return self


class PersonaDossier(StrictModel):
    protocol_version: Literal["persona-dossier/0.1"] = "persona-dossier/0.1"
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
    topics: tuple[PersonaDossierTopic, ...] = Field(min_length=14, max_length=14)
    model_enrichment: Literal["not_used"] = "not_used"
    calibration_status: Literal["not_calibrated"] = "not_calibrated"
    semantic_adoption: Literal["not_established"] = "not_established"
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    authority: Literal["none"] = "none"
    persistent: Literal[False] = False
    dossier_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def dossier_is_canonical(self) -> PersonaDossier:
        if tuple(topic.key for topic in self.topics) != DOSSIER_TOPIC_ORDER:
            raise ValueError("persona dossier topics are not in canonical order")
        expected_class = (
            DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.DERIVED_IDENTITY
        )
        if self.data_class != expected_class:
            raise ValueError("persona dossier data class contradicts its pack mode")
        payload = self.model_dump(mode="json", exclude={"dossier_sha256"})
        if self.dossier_sha256 != canonical_sha256(payload):
            raise ValueError("persona dossier hash does not match")
        return self


def _candidate_state(
    candidates: tuple[PersonaDossierCandidate, ...],
) -> Literal["literal_candidates", "conflicted_candidates", "unknown"]:
    if not candidates:
        return "unknown"
    if any(item.truth_status == "conflicted_observation" for item in candidates):
        return "conflicted_candidates"
    return "literal_candidates"
