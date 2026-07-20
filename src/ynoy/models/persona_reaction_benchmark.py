from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.full_persona import FullCorpusContext
from ynoy.util import canonical_sha256

type Digest = str
type ReactionSignal = Literal[
    "correction",
    "evidence_demand",
    "scope_change",
    "decision",
    "outcome_feedback",
]
type ReactionPrediction = ReactionSignal | Literal["abstain"]
type ReactionArm = Literal[
    "generic_local_8b",
    "history_majority",
    "chronological_recency",
    "lexical_retrieval",
    "static_profile",
    "structured_persona",
]
type ResponseExcerpt = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=768)
]

REACTION_SIGNALS: tuple[ReactionSignal, ...] = (
    "correction",
    "evidence_demand",
    "scope_change",
    "decision",
    "outcome_feedback",
)
REACTION_ARMS: tuple[ReactionArm, ...] = (
    "generic_local_8b",
    "history_majority",
    "chronological_recency",
    "lexical_retrieval",
    "static_profile",
    "structured_persona",
)
DETERMINISTIC_REACTION_ARMS: tuple[ReactionArm, ...] = REACTION_ARMS[1:5]


class PersonaReactionHistory(StrictModel):
    history_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    lineage_component_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    context: tuple[FullCorpusContext, ...] = Field(min_length=1, max_length=4)
    observed_response_excerpt: ResponseExcerpt
    content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    observed_signal: ReactionSignal
    data_class: DataClass
    synthetic: bool
    history_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def history_is_canonical(self) -> PersonaReactionHistory:
        _require_data_class(self.data_class, self.synthetic)
        _require_hash(self, "history_sha256")
        return self


class PersonaReactionCase(StrictModel):
    case_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    lineage_component_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    context: tuple[FullCorpusContext, ...] = Field(min_length=1, max_length=4)
    data_class: DataClass
    synthetic: bool
    case_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def case_is_canonical(self) -> PersonaReactionCase:
        _require_data_class(self.data_class, self.synthetic)
        _require_hash(self, "case_sha256")
        return self


class PersonaReactionTargetLocator(StrictModel):
    case_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    locator_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def locator_is_canonical(self) -> PersonaReactionTargetLocator:
        _require_hash(self, "locator_sha256")
        return self


class PersonaReactionManifest(StrictModel):
    protocol_version: Literal["sealed-reaction-benchmark/0.1"] = "sealed-reaction-benchmark/0.1"
    source_run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    source_holdout_freeze_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    temporal_cutoff: datetime
    development_history_ids: tuple[Digest, ...] = Field(min_length=1, max_length=8_192)
    development_history_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_case_ids: tuple[Digest, ...] = Field(min_length=24, max_length=24)
    sealed_case_set_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_cluster_count: int = Field(ge=8, le=24)
    max_cases_per_component: Literal[3] = 3
    signal_tie_order: tuple[ReactionSignal, ...] = REACTION_SIGNALS
    arms: tuple[ReactionArm, ...] = REACTION_ARMS
    data_class: DataClass
    synthetic: bool
    evidence_authentication: Literal["synthetic_fixture", "verified_full_corpus_store"]
    split_scope: Literal["internal_pre_protected_holdout"] = "internal_pre_protected_holdout"
    label_semantics: Literal["lexical_proxy_not_user_validated"] = (
        "lexical_proxy_not_user_validated"
    )
    protected_future_holdout_used: Literal[False] = False
    target_visible_to_predictors: Literal[False] = False
    local_only: Literal[True] = True
    external_calls: tuple[()] = ()
    persona_identity_claimed: Literal[False] = False
    calibration_used: Literal[False] = False
    semantic_adoption_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def manifest_is_canonical(self) -> PersonaReactionManifest:
        if self.signal_tie_order != REACTION_SIGNALS or self.arms != REACTION_ARMS:
            raise ValueError("reaction benchmark protocol order changed")
        if len(set(self.development_history_ids)) != len(self.development_history_ids):
            raise ValueError("reaction development history identifiers repeat")
        if len(set(self.sealed_case_ids)) != len(self.sealed_case_ids):
            raise ValueError("reaction sealed case identifiers repeat")
        if set(self.development_history_ids) & set(self.sealed_case_ids):
            raise ValueError("reaction development and sealed identifiers overlap")
        _require_data_class(self.data_class, self.synthetic)
        expected_auth = "synthetic_fixture" if self.synthetic else "verified_full_corpus_store"
        if self.evidence_authentication != expected_auth:
            raise ValueError("reaction evidence authentication contradicts its mode")
        _require_hash(self, "manifest_sha256")
        return self


class PersonaReactionTargetSeal(StrictModel):
    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    locators: tuple[PersonaReactionTargetLocator, ...] = Field(min_length=24, max_length=24)
    targets_revealed: Literal[False] = False
    seal_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def seal_is_canonical(self) -> PersonaReactionTargetSeal:
        case_ids = tuple(item.case_id for item in self.locators)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("reaction target locators repeat")
        _require_hash(self, "seal_sha256")
        return self


class PersonaReactionTarget(StrictModel):
    case_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    label: ReactionSignal
    target_content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    target_evidence_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    target_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def target_is_canonical(self) -> PersonaReactionTarget:
        _require_hash(self, "target_sha256")
        return self


class PersonaReactionArmPrediction(StrictModel):
    arm: ReactionArm
    case_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    predicted_label: ReactionPrediction
    abstained: bool
    evidence_ids: tuple[Digest, ...] = Field(max_length=8)
    ranking_score: float | None = Field(default=None, ge=0.0, le=1.0)
    target_seen: Literal[False] = False
    target_text: Literal[None] = None
    persona_identity: Literal[False] = False
    calibration_used: Literal[False] = False
    semantic_adoption: Literal[False] = False
    core_eligible: Literal[False] = False
    prediction_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def prediction_is_canonical(self) -> PersonaReactionArmPrediction:
        if self.abstained != (self.predicted_label == "abstain"):
            raise ValueError("reaction abstention flag contradicts its prediction")
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("reaction prediction evidence identifiers repeat")
        _require_hash(self, "prediction_sha256")
        return self


class PersonaReactionBaselineRun(StrictModel):
    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    arms: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]]
    persona_identity_claimed: Literal[False] = False
    calibration_used: Literal[False] = False
    semantic_adoption_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    comparison_complete: Literal[False] = False
    status: Literal["deterministic_controls_only"] = "deterministic_controls_only"
    run_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def run_is_canonical(self) -> PersonaReactionBaselineRun:
        if set(self.arms) != set(DETERMINISTIC_REACTION_ARMS):
            raise ValueError("reaction baseline arms are incomplete")
        orders = {tuple(item.case_id for item in values) for values in self.arms.values()}
        if len(orders) != 1 or any(len(values) != 24 for values in self.arms.values()):
            raise ValueError("reaction baseline cases are inconsistent")
        _require_hash(self, "run_sha256")
        return self


def _require_hash(model: StrictModel, field: str) -> None:
    expected = canonical_sha256(model.model_dump(mode="json", exclude={field}))
    if getattr(model, field) != expected:
        raise ValueError(f"{field} does not match its canonical payload")


def _require_data_class(data_class: DataClass, synthetic: bool) -> None:
    expected = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS
    if data_class != expected:
        raise ValueError("reaction data class contradicts its mode")
