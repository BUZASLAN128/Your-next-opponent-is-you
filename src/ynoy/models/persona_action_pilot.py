from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_harvest import HarvestContextMessage, HarvestSignal
from ynoy.util import canonical_sha256

ActionSignal = HarvestSignal
ActionPrediction = ActionSignal | Literal["abstain"]
PilotArm = Literal["generic", "personalized"]


class ActionPilotHistory(StrictModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    source_receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    context: tuple[HarvestContextMessage, ...]
    focus: str = Field(min_length=1)
    primary_signal: ActionSignal


class ActionPilotCase(StrictModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    source_receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    context: tuple[HarvestContextMessage, ...]


class ActionPilotTarget(StrictModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    primary_signal: ActionSignal
    target_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> ActionPilotTarget:
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"target_sha256"}))
        if self.target_sha256 != expected:
            raise ValueError("action target receipt does not match")
        return self


class ActionPilotManifest(StrictModel):
    protocol_version: Literal["observable-action-pilot/0.1"] = "observable-action-pilot/0.1"
    source_study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorship_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    history_case_ids: tuple[str, ...] = Field(min_length=6, max_length=6)
    sealed_case_ids: tuple[str, ...] = Field(min_length=6, max_length=6)
    signal_tie_order: tuple[ActionSignal, ...] = Field(min_length=6, max_length=6)
    target_visible_to_predictor: Literal[False] = False
    represented_user_authorship_only: Literal[True] = True
    semantic_adoption_claimed: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> ActionPilotManifest:
        if set(self.history_case_ids) & set(self.sealed_case_ids):
            raise ValueError("action pilot history and sealed cases overlap")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"manifest_sha256"}))
        if self.manifest_sha256 != expected:
            raise ValueError("action pilot manifest receipt does not match")
        return self


class ActionPilotPrediction(StrictModel):
    arm: PilotArm
    case_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    predicted_signal: ActionPrediction
    ranking_score: float = Field(ge=0.0, le=1.0)
    model: str = Field(min_length=1)
    target_seen: Literal[False] = False


class ActionPredictionFreeze(StrictModel):
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generic_predictions: tuple[ActionPilotPrediction, ...] = Field(min_length=6, max_length=6)
    personalized_predictions: tuple[ActionPilotPrediction, ...] = Field(min_length=6, max_length=6)
    targets_revealed: Literal[False] = False
    freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> ActionPredictionFreeze:
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"freeze_sha256"}))
        if self.freeze_sha256 != expected:
            raise ValueError("action prediction freeze receipt does not match")
        return self


class ActionArmMetrics(StrictModel):
    arm: PilotArm
    case_count: Literal[6] = 6
    correct_count: int = Field(ge=0, le=6)
    abstained_count: int = Field(ge=0, le=6)
    accuracy: float = Field(ge=0.0, le=1.0)


class ActionPilotRun(StrictModel):
    status: Literal["positive_directional", "negative_directional", "inconclusive"]
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prediction_freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generic: ActionArmMetrics
    personalized: ActionArmMetrics
    paired_correct_difference: int = Field(ge=-6, le=6)
    reason: str = Field(min_length=1)
    observable_action_only: Literal[True] = True
    calibrated: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> ActionPilotRun:
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"run_sha256"}))
        if self.run_sha256 != expected:
            raise ValueError("action pilot run receipt does not match")
        return self


class ActionPilotAudit(StrictModel):
    original_run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    history_majority_correct: int = Field(ge=0, le=6)
    history_recent_correct: int = Field(ge=0, le=6)
    strongest_baseline_correct: int = Field(ge=0, le=6)
    corrected_status: Literal["positive_directional", "negative_directional", "inconclusive"]
    reason: str = Field(min_length=1)
    original_result_superseded: Literal[True] = True
    persona_quality_claimed: Literal[False] = False
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> ActionPilotAudit:
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"audit_sha256"}))
        if self.audit_sha256 != expected:
            raise ValueError("action pilot audit receipt does not match")
        return self
