from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_reaction_benchmark import (
    REACTION_ARMS,
    PersonaReactionArmPrediction,
    PersonaReactionTarget,
    PersonaReactionTargetSeal,
    ReactionArm,
)
from ynoy.util import canonical_sha256

type Digest = str
type ComparisonStatus = Literal[
    "positive_directional",
    "negative_directional",
    "inconclusive",
]


class PersonaReactionModelRun(StrictModel):
    """Two local-model arms produced before any sealed target is opened."""

    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    model: str = Field(min_length=1, max_length=256)
    revision: str = Field(min_length=1, max_length=256)
    artifact_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    decode_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    predictions: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]]
    source_synthetic: bool
    local_attested: Literal[True] = True
    artifact_file_verified: bool
    endpoint_authentication: Literal["not_cryptographically_authenticated"] = (
        "not_cryptographically_authenticated"
    )
    targets_revealed: Literal[False] = False
    calibration_used: Literal[False] = False
    persona_identity_claimed: Literal[False] = False
    run_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def model_run_is_canonical(self) -> PersonaReactionModelRun:
        expected_arms = ("generic_local_8b", "structured_persona")
        if set(self.predictions) != set(expected_arms):
            raise ValueError("reaction model arms are incomplete")
        orders = {tuple(item.case_id for item in values) for values in self.predictions.values()}
        if len(orders) != 1 or any(len(values) != 24 for values in self.predictions.values()):
            raise ValueError("reaction model cases are inconsistent")
        for arm, values in self.predictions.items():
            if any(item.arm != arm or item.target_seen for item in values):
                raise ValueError("reaction model prediction binding changed")
        if not self.source_synthetic and not self.artifact_file_verified:
            raise ValueError("private reaction run requires a verified local artifact file")
        _require_hash(self, "run_sha256")
        return self


class PersonaReactionPredictionFreeze(StrictModel):
    """All six arm predictions and evaluation constants frozen before scoring."""

    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    target_seal_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    arms: tuple[ReactionArm, ...] = REACTION_ARMS
    predictions: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]]
    model_bindings: dict[ReactionArm, str]
    case_clusters: dict[Digest, Digest]
    matched_case_ids: tuple[Digest, ...] = Field(min_length=18, max_length=18)
    synthetic: bool
    upstream_run_sha256s: tuple[Digest, ...] = Field(max_length=2)
    abstention_loss: float = Field(default=0.5, ge=0.0, le=1.0)
    minimum_coverage: float = Field(default=0.75, gt=0.0, le=1.0)
    minimum_effect: float = Field(default=0.041666666666666664, ge=0.0, le=1.0)
    bootstrap_resamples: Literal[2000] = 2000
    bootstrap_alpha: float = Field(default=0.01, gt=0.0, lt=1.0)
    bootstrap_seed: Literal[20260719] = 20260719
    targets_revealed: Literal[False] = False
    calibrated: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    freeze_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def freeze_is_canonical(self) -> PersonaReactionPredictionFreeze:
        if self.arms != REACTION_ARMS:
            raise ValueError("reaction freeze arm order changed")
        if set(self.predictions) != set(REACTION_ARMS) or set(self.model_bindings) != set(
            REACTION_ARMS
        ):
            raise ValueError("reaction freeze bindings are incomplete")
        orders = {tuple(item.case_id for item in values) for values in self.predictions.values()}
        if len(orders) != 1 or any(len(values) != 24 for values in self.predictions.values()):
            raise ValueError("reaction freeze cases are inconsistent")
        case_order = next(iter(orders))
        if set(self.case_clusters) != set(case_order) or len(set(self.case_clusters.values())) < 8:
            raise ValueError("reaction freeze cluster binding is incomplete")
        if self.matched_case_ids != case_order[:18]:
            raise ValueError("reaction freeze matched support changed")
        for arm, values in self.predictions.items():
            if any(item.arm != arm or item.target_seen for item in values):
                raise ValueError("reaction freeze prediction binding changed")
        if any(not value.strip() or len(value) > 512 for value in self.model_bindings.values()):
            raise ValueError("reaction freeze model binding is invalid")
        constants = (
            self.abstention_loss,
            self.minimum_coverage,
            self.minimum_effect,
            self.bootstrap_alpha,
        )
        if constants != (0.5, 0.75, 1 / 24, 0.01):
            raise ValueError("reaction freeze evaluation constants changed")
        if (not self.synthetic and len(self.upstream_run_sha256s) != 2) or any(
            not re.fullmatch(r"[0-9a-f]{64}", value) for value in self.upstream_run_sha256s
        ):
            raise ValueError("reaction freeze upstream binding is invalid")
        _require_hash(self, "freeze_sha256")
        return self


class PersonaReactionTargetSet(StrictModel):
    """Hash-only targets opened from verified evidence after prediction freeze."""

    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    prediction_freeze_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    synthetic: bool
    target_seal: PersonaReactionTargetSeal
    targets: tuple[PersonaReactionTarget, ...] = Field(min_length=24, max_length=24)
    targets_revealed: Literal[True] = True
    raw_target_text_persisted: Literal[False] = False
    target_set_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def target_set_is_canonical(self) -> PersonaReactionTargetSet:
        locators = self.target_seal.locators
        pairs = zip(locators, self.targets, strict=True)
        if self.target_seal.manifest_sha256 != self.manifest_sha256 or any(
            target.case_id != locator.case_id
            or target.target_evidence_sha256 != locator.evidence_sha256
            for locator, target in pairs
        ):
            raise ValueError("reaction target set does not match its sealed locators")
        _require_hash(self, "target_set_sha256")
        return self


class PersonaReactionComparisonResult(StrictModel):
    """Proxy-label comparison; it is never a calibrated persona-fidelity claim."""

    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    prediction_freeze_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    target_set_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: Literal[24] = 24
    cluster_count: int = Field(ge=8, le=24)
    correct: dict[ReactionArm, int]
    wrong: dict[ReactionArm, int]
    abstained: dict[ReactionArm, int]
    coverage: dict[ReactionArm, float]
    risk: dict[ReactionArm, float]
    matched_coverage_available: dict[ReactionArm, bool]
    matched_risk: dict[ReactionArm, float | None]
    matched_case_count: Literal[18] = 18
    matched_cluster_count: int = Field(ge=1, le=18)
    paired_cluster_upper: dict[ReactionArm, float | None]
    status: ComparisonStatus
    reason: str = Field(min_length=1, max_length=512)
    label_semantics: Literal["lexical_proxy_not_user_validated"] = (
        "lexical_proxy_not_user_validated"
    )
    protected_future_holdout_used: Literal[False] = False
    calibrated: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    result_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def result_is_canonical(self) -> PersonaReactionComparisonResult:
        maps = (
            self.correct,
            self.wrong,
            self.abstained,
            self.coverage,
            self.risk,
            self.matched_coverage_available,
            self.matched_risk,
        )
        if any(set(value) != set(REACTION_ARMS) for value in maps):
            raise ValueError("reaction result arms are incomplete")
        paired_arms = {arm for arm in REACTION_ARMS if arm != "structured_persona"}
        if set(self.paired_cluster_upper) != paired_arms:
            raise ValueError("reaction paired diagnostics are incomplete")
        if any(
            self.correct[arm] + self.wrong[arm] + self.abstained[arm] != self.case_count
            for arm in REACTION_ARMS
        ):
            raise ValueError("reaction result counts do not reconcile")
        _require_hash(self, "result_sha256")
        return self


def _require_hash(model: StrictModel, field: str) -> None:
    expected = canonical_sha256(model.model_dump(mode="json", exclude={field}))
    if getattr(model, field) != expected:
        raise ValueError(f"{field} does not match its canonical payload")
