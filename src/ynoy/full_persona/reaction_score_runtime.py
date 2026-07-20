from __future__ import annotations

import math
import random
from collections.abc import Mapping

from pydantic import ValidationError

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.full_persona.reaction_contracts import seal_model
from ynoy.models.persona_reaction_benchmark import (
    REACTION_ARMS,
    PersonaReactionArmPrediction,
    ReactionArm,
    ReactionSignal,
)
from ynoy.models.persona_reaction_results import (
    ComparisonStatus,
    PersonaReactionComparisonResult,
    PersonaReactionPredictionFreeze,
    PersonaReactionTargetSet,
)


def score_reaction_predictions(
    freeze: PersonaReactionPredictionFreeze,
    target_set: PersonaReactionTargetSet,
) -> PersonaReactionComparisonResult:
    """Score the immutable freeze on one common, label-blind matched support."""
    safe_freeze, safe_target_set = _validated_inputs(freeze, target_set)
    if not safe_freeze.synthetic or not safe_target_set.synthetic:
        raise PolicyViolation(
            "reaction_score_verified_entrypoint_required",
            "Private scoring requires source-rematerialization through the verified entrypoint.",
        )
    return _score_synthetic(safe_freeze, safe_target_set)


def _score_synthetic(
    safe_freeze: PersonaReactionPredictionFreeze,
    safe_target_set: PersonaReactionTargetSet,
) -> PersonaReactionComparisonResult:
    if not safe_freeze.synthetic or not safe_target_set.synthetic:
        raise PolicyViolation(
            "reaction_score_verified_entrypoint_required",
            "Private scoring requires the verified-store benchmark entrypoint.",
        )
    targets = {item.case_id: item.label for item in safe_target_set.targets}
    losses = {
        arm: _arm_losses(values, targets, safe_freeze.abstention_loss)
        for arm, values in safe_freeze.predictions.items()
    }
    correct = _count_by_arm(safe_freeze, targets, "correct")
    wrong = _count_by_arm(safe_freeze, targets, "wrong")
    abstained = _count_by_arm(safe_freeze, targets, "abstained")
    coverage = {
        arm: (len(values) - abstained[arm]) / len(values)
        for arm, values in safe_freeze.predictions.items()
    }
    risk = {arm: sum(values.values()) / len(values) for arm, values in losses.items()}
    matched_available, matched_risk = _matched_risks(safe_freeze, losses)
    paired = _paired_diagnostics(safe_freeze, losses, matched_available)
    status, reason = _status(safe_freeze, matched_available, matched_risk, paired)
    return _result(
        safe_freeze,
        safe_target_set,
        correct,
        wrong,
        abstained,
        coverage,
        risk,
        matched_available,
        matched_risk,
        paired,
        status,
        reason,
    )


def _validated_inputs(
    freeze: PersonaReactionPredictionFreeze,
    target_set: PersonaReactionTargetSet,
) -> tuple[PersonaReactionPredictionFreeze, PersonaReactionTargetSet]:
    try:
        safe_freeze = PersonaReactionPredictionFreeze.model_validate(freeze.model_dump(mode="json"))
        safe_targets = PersonaReactionTargetSet.model_validate(target_set.model_dump(mode="json"))
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_score_input_invalid", "Reaction score input is invalid."
        ) from exc
    expected = tuple(item.case_id for item in safe_freeze.predictions["generic_local_8b"])
    invalid = (
        tuple(item.case_id for item in safe_targets.targets) != expected
        or len(set(expected)) != 24
        or safe_targets.manifest_sha256 != safe_freeze.manifest_sha256
        or safe_targets.prediction_freeze_sha256 != safe_freeze.freeze_sha256
        or safe_targets.target_seal.seal_sha256 != safe_freeze.target_seal_sha256
    )
    if invalid:
        raise DataValidationError(
            "reaction_score_target_invalid", "Reaction targets do not match the prediction freeze."
        )
    return safe_freeze, safe_targets


def _arm_losses(
    predictions: tuple[PersonaReactionArmPrediction, ...],
    targets: Mapping[str, ReactionSignal],
    abstention_loss: float,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in predictions:
        result[item.case_id] = (
            abstention_loss
            if item.abstained
            else float(item.predicted_label != targets[item.case_id])
        )
    return result


def _count_by_arm(
    freeze: PersonaReactionPredictionFreeze,
    targets: Mapping[str, ReactionSignal],
    kind: str,
) -> dict[ReactionArm, int]:
    result: dict[ReactionArm, int] = {}
    for arm, values in freeze.predictions.items():
        if kind == "abstained":
            result[arm] = sum(item.abstained for item in values)
        elif kind == "correct":
            result[arm] = sum(
                not item.abstained and item.predicted_label == targets[item.case_id]
                for item in values
            )
        else:
            result[arm] = sum(
                not item.abstained and item.predicted_label != targets[item.case_id]
                for item in values
            )
    return result


def _matched_risks(
    freeze: PersonaReactionPredictionFreeze,
    losses: dict[ReactionArm, dict[str, float]],
) -> tuple[dict[ReactionArm, bool], dict[ReactionArm, float | None]]:
    support = set(freeze.matched_case_ids)
    available = {
        arm: all(not item.abstained for item in values if item.case_id in support)
        for arm, values in freeze.predictions.items()
    }
    risk = {
        arm: (
            sum(values[case_id] for case_id in freeze.matched_case_ids)
            / len(freeze.matched_case_ids)
            if available[arm]
            else None
        )
        for arm, values in losses.items()
    }
    return available, risk


def _paired_diagnostics(
    freeze: PersonaReactionPredictionFreeze,
    losses: dict[ReactionArm, dict[str, float]],
    available: dict[ReactionArm, bool],
) -> dict[ReactionArm, float | None]:
    structured = losses["structured_persona"]
    controls = tuple(arm for arm in REACTION_ARMS if arm != "structured_persona")
    return {
        arm: (
            _cluster_bootstrap_upper(
                freeze,
                {
                    case_id: structured[case_id] - losses[arm][case_id]
                    for case_id in freeze.matched_case_ids
                },
                arm_index=index,
            )
            if available["structured_persona"] and available[arm]
            else None
        )
        for index, arm in enumerate(controls)
    }


def _cluster_bootstrap_upper(
    freeze: PersonaReactionPredictionFreeze,
    differences: dict[str, float],
    *,
    arm_index: int,
) -> float:
    grouped: dict[str, list[float]] = {}
    for case_id, value in differences.items():
        grouped.setdefault(freeze.case_clusters[case_id], []).append(value)
    clusters = tuple(sorted(grouped))
    generator = random.Random(freeze.bootstrap_seed + arm_index)
    samples: list[float] = []
    for _ in range(freeze.bootstrap_resamples):
        selected = tuple(generator.choice(clusters) for _ in clusters)
        values = tuple(value for cluster in selected for value in grouped[cluster])
        samples.append(sum(values) / len(values))
    samples.sort()
    index = min(
        len(samples) - 1,
        math.ceil((1.0 - freeze.bootstrap_alpha) * len(samples)) - 1,
    )
    return float(samples[index])


def _status(
    freeze: PersonaReactionPredictionFreeze,
    available: dict[ReactionArm, bool],
    risk: dict[ReactionArm, float | None],
    paired: dict[ReactionArm, float | None],
) -> tuple[ComparisonStatus, str]:
    if not all(available.values()):
        return "inconclusive", "At least one arm lacks the frozen matched-coverage support."
    structured = risk["structured_persona"]
    if structured is None or any(value is None for value in paired.values()):
        return "inconclusive", "Matched-coverage risk could not be computed."
    if all(value <= -freeze.minimum_effect for value in paired.values() if value is not None):
        return (
            "positive_directional",
            "Structured predictions beat every control under the frozen cluster diagnostic.",
        )
    controls = tuple(
        value for arm, value in risk.items() if arm != "structured_persona" and value is not None
    )
    if min(controls) + freeze.minimum_effect <= structured:
        return "negative_directional", "A frozen control has materially lower proxy-label risk."
    return "inconclusive", "The matched cluster evidence does not separate structured persona."


def _result(
    freeze: PersonaReactionPredictionFreeze,
    targets: PersonaReactionTargetSet,
    correct: dict[ReactionArm, int],
    wrong: dict[ReactionArm, int],
    abstained: dict[ReactionArm, int],
    coverage: dict[ReactionArm, float],
    risk: dict[ReactionArm, float],
    matched_available: dict[ReactionArm, bool],
    matched_risk: dict[ReactionArm, float | None],
    paired: dict[ReactionArm, float | None],
    status: ComparisonStatus,
    reason: str,
) -> PersonaReactionComparisonResult:
    payload: dict[str, object] = {
        "manifest_sha256": freeze.manifest_sha256,
        "prediction_freeze_sha256": freeze.freeze_sha256,
        "target_set_sha256": targets.target_set_sha256,
        "case_count": 24,
        "cluster_count": len(set(freeze.case_clusters.values())),
        "correct": correct,
        "wrong": wrong,
        "abstained": abstained,
        "coverage": coverage,
        "risk": risk,
        "matched_coverage_available": matched_available,
        "matched_risk": matched_risk,
        "matched_case_count": len(freeze.matched_case_ids),
        "matched_cluster_count": len(
            {freeze.case_clusters[item] for item in freeze.matched_case_ids}
        ),
        "paired_cluster_upper": paired,
        "status": status,
        "reason": reason,
        "label_semantics": "lexical_proxy_not_user_validated",
        "protected_future_holdout_used": False,
        "calibrated": False,
        "persona_quality_claimed": False,
        "automatic_core_promotion": False,
    }
    return seal_model(PersonaReactionComparisonResult, payload, "result_sha256")
