from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pydantic import BaseModel

from ynoy.errors import DataValidationError
from ynoy.models.harvest_authorship import HarvestAuthorshipReceipt
from ynoy.models.persona_action_pilot import (
    ActionArmMetrics,
    ActionPilotAudit,
    ActionPilotCase,
    ActionPilotHistory,
    ActionPilotManifest,
    ActionPilotPrediction,
    ActionPilotRun,
    ActionPilotTarget,
    ActionPredictionFreeze,
)
from ynoy.models.persona_harvest import HarvestCandidate, HarvestCheckpoint
from ynoy.persona_study.action_pilot_inputs import (
    SIGNAL_TIE_ORDER,
    action_case,
    action_history,
    primary_signal,
    validate_action_split,
)
from ynoy.util import canonical_sha256

_HISTORY_SIZE = 6
_SEALED_SIZE = 6


def prepare_action_pilot(
    checkpoint: HarvestCheckpoint,
    authorship_receipt: HarvestAuthorshipReceipt,
) -> tuple[
    ActionPilotManifest,
    tuple[ActionPilotHistory, ...],
    tuple[ActionPilotCase, ...],
    tuple[ActionPilotTarget, ...],
]:
    selected = _validated_candidates(checkpoint, authorship_receipt)
    ordered = tuple(sorted(selected, key=lambda item: (item.event_time, item.candidate_id)))
    history_candidates = ordered[:_HISTORY_SIZE]
    sealed_candidates = ordered[_HISTORY_SIZE:]
    validate_action_split(history_candidates, sealed_candidates)
    history = tuple(action_history(item) for item in history_candidates)
    cases = tuple(action_case(item) for item in sealed_candidates)
    targets = tuple(_target(item) for item in sealed_candidates)
    manifest = _manifest(authorship_receipt, history, cases)
    return manifest, history, cases, targets


def freeze_action_predictions(
    manifest: ActionPilotManifest,
    generic_predictions: tuple[ActionPilotPrediction, ...],
    personalized_predictions: tuple[ActionPilotPrediction, ...],
) -> ActionPredictionFreeze:
    expected = manifest.sealed_case_ids
    _validate_predictions(generic_predictions, "generic", expected)
    _validate_predictions(personalized_predictions, "personalized", expected)
    generic_models = {item.model for item in generic_predictions}
    personal_models = {item.model for item in personalized_predictions}
    if len(generic_models) != 1 or generic_models != personal_models:
        raise DataValidationError(
            "action_pilot_model_mismatch",
            "Both pilot arms must use the same single pinned predictor model.",
        )
    payload = {
        "manifest_sha256": manifest.manifest_sha256,
        "generic_predictions": generic_predictions,
        "personalized_predictions": personalized_predictions,
        "targets_revealed": False,
    }
    return _sealed(ActionPredictionFreeze, payload, "freeze_sha256")


def score_action_pilot(
    manifest: ActionPilotManifest,
    prediction_freeze: ActionPredictionFreeze,
    history: tuple[ActionPilotHistory, ...],
    targets: tuple[ActionPilotTarget, ...],
) -> ActionPilotRun:
    if prediction_freeze.manifest_sha256 != manifest.manifest_sha256:
        raise DataValidationError(
            "action_pilot_freeze_mismatch", "Prediction freeze belongs to another pilot."
        )
    target_map = {item.case_id: item for item in targets}
    if tuple(item.case_id for item in targets) != manifest.sealed_case_ids:
        raise DataValidationError(
            "action_pilot_target_mismatch", "Targets do not match the frozen case order."
        )
    generic = _metrics("generic", prediction_freeze.generic_predictions, target_map)
    personalized = _metrics("personalized", prediction_freeze.personalized_predictions, target_map)
    difference = personalized.correct_count - generic.correct_count
    majority, recent = _history_baseline_scores(history, targets)
    status, reason = _directional_status(generic, personalized, majority, recent)
    payload = {
        "status": status,
        "manifest_sha256": manifest.manifest_sha256,
        "prediction_freeze_sha256": prediction_freeze.freeze_sha256,
        "generic": generic,
        "personalized": personalized,
        "paired_correct_difference": difference,
        "reason": reason,
        "observable_action_only": True,
        "calibrated": False,
        "persona_quality_claimed": False,
        "automatic_core_promotion": False,
    }
    return _sealed(ActionPilotRun, payload, "run_sha256")


def audit_action_pilot(
    run: ActionPilotRun,
    history: tuple[ActionPilotHistory, ...],
    targets: tuple[ActionPilotTarget, ...],
) -> ActionPilotAudit:
    majority, recent = _history_baseline_scores(history, targets)
    status, reason = _directional_status(run.generic, run.personalized, majority, recent)
    payload = {
        "original_run_sha256": run.run_sha256,
        "history_majority_correct": majority,
        "history_recent_correct": recent,
        "strongest_baseline_correct": max(run.generic.correct_count, majority, recent),
        "corrected_status": status,
        "reason": reason,
        "original_result_superseded": True,
        "persona_quality_claimed": False,
    }
    return _sealed(ActionPilotAudit, payload, "audit_sha256")


def _validated_candidates(
    checkpoint: HarvestCheckpoint, receipt: HarvestAuthorshipReceipt
) -> tuple[HarvestCandidate, ...]:
    candidates = checkpoint.candidates[:12]
    candidate_ids = tuple(item.candidate_id for item in candidates)
    candidate_hashes = tuple(item.candidate_sha256 for item in candidates)
    valid = (
        len(candidates) == _HISTORY_SIZE + _SEALED_SIZE
        and checkpoint.checkpoint_sha256 == receipt.checkpoint_sha256
        and checkpoint.cursor.revision == receipt.revision
        and checkpoint.cursor.run_id == receipt.run_id
        and checkpoint.cursor.source_study_id == receipt.source_study_id
        and candidate_ids == receipt.candidate_ids
        and candidate_hashes == receipt.candidate_sha256s
        and receipt.authorships == ("self",) * 12
    )
    if not valid:
        raise DataValidationError(
            "action_pilot_authorship_mismatch",
            "The pilot input is not the exact twelve-card authorship receipt.",
        )
    return candidates


def _target(item: HarvestCandidate) -> ActionPilotTarget:
    payload: dict[str, object] = {
        "case_id": item.candidate_id,
        "primary_signal": primary_signal(item),
    }
    return _sealed(ActionPilotTarget, payload, "target_sha256")


def _manifest(
    receipt: HarvestAuthorshipReceipt,
    history: tuple[ActionPilotHistory, ...],
    cases: tuple[ActionPilotCase, ...],
) -> ActionPilotManifest:
    payload = {
        "source_study_id": receipt.source_study_id,
        "run_id": receipt.run_id,
        "authorship_receipt_sha256": receipt.receipt_sha256,
        "checkpoint_sha256": receipt.checkpoint_sha256,
        "history_case_ids": tuple(item.case_id for item in history),
        "sealed_case_ids": tuple(item.case_id for item in cases),
        "signal_tie_order": SIGNAL_TIE_ORDER,
        "target_visible_to_predictor": False,
        "represented_user_authorship_only": True,
        "semantic_adoption_claimed": False,
        "persona_quality_claimed": False,
    }
    return _sealed(ActionPilotManifest, payload, "manifest_sha256")


def _validate_predictions(
    predictions: tuple[ActionPilotPrediction, ...],
    arm: str,
    expected_ids: tuple[str, ...],
) -> None:
    if (
        tuple(item.case_id for item in predictions) != expected_ids
        or any(item.arm != arm for item in predictions)
        or len({item.case_id for item in predictions}) != len(predictions)
        or any(item.target_seen for item in predictions)
    ):
        raise DataValidationError(
            "action_pilot_prediction_mismatch",
            "Predictions do not match the exact target-free case manifest.",
        )


def _metrics(
    arm: str,
    predictions: tuple[ActionPilotPrediction, ...],
    targets: dict[str, ActionPilotTarget],
) -> ActionArmMetrics:
    correct = sum(
        item.predicted_signal == targets[item.case_id].primary_signal for item in predictions
    )
    abstained = sum(item.predicted_signal == "abstain" for item in predictions)
    return ActionArmMetrics(
        arm=cast(Any, arm),
        correct_count=correct,
        abstained_count=abstained,
        accuracy=correct / len(predictions),
    )


def _directional_status(
    generic: ActionArmMetrics,
    personalized: ActionArmMetrics,
    majority_correct: int,
    recent_correct: int,
) -> tuple[str, str]:
    if personalized.abstained_count == 6 and generic.abstained_count == 6:
        return "inconclusive", "Both arms abstained on every sealed case."
    strongest = max(generic.correct_count, majority_correct, recent_correct)
    if personalized.correct_count > strongest:
        return "positive_directional", "Personalized predictions beat every frozen baseline."
    if personalized.correct_count < strongest:
        return "negative_directional", "A frozen baseline beat personalized predictions."
    return "inconclusive", "Personalized predictions tied the strongest frozen baseline."


def _history_baseline_scores(
    history: tuple[ActionPilotHistory, ...], targets: tuple[ActionPilotTarget, ...]
) -> tuple[int, int]:
    if tuple(item.case_id for item in history) == () or len(history) != 6:
        raise DataValidationError(
            "action_pilot_history_invalid", "Scoring requires the exact six history cases."
        )
    counts = {signal: 0 for signal in SIGNAL_TIE_ORDER}
    for item in history:
        counts[item.primary_signal] += 1
    majority = sorted(SIGNAL_TIE_ORDER, key=lambda signal: -counts[signal])[0]
    recent = history[-1].primary_signal
    return (
        sum(item.primary_signal == majority for item in targets),
        sum(item.primary_signal == recent for item in targets),
    )


def _sealed[ModelT: BaseModel](
    model: type[ModelT], payload: Mapping[str, object], hash_field: str
) -> ModelT:
    draft = cast(Any, model).model_construct(**dict(payload), **{hash_field: "0" * 64})
    value = draft.model_dump(mode="json", exclude={hash_field})
    return model.model_validate({**value, hash_field: canonical_sha256(value)})
