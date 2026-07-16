from __future__ import annotations

from collections.abc import Mapping, Sequence

from ynoy.models import DecisionLabel, Prediction


def calculate_metrics(
    predictions: Sequence[Prediction], targets: Mapping[str, DecisionLabel]
) -> dict[str, float | int | str | bool]:
    total = len(predictions)
    if not total:
        return _empty_metrics()
    labels = sorted({targets[item.case_id] for item in predictions}, key=lambda item: item.value)
    correct, covered, covered_correct, loss = _outcome_totals(predictions, targets)
    f1_values, recalls = _class_metrics(predictions, targets, labels)
    fatal_count = sum(prediction.fatal_gate is not None for prediction in predictions)
    return {
        "total": total,
        "accuracy": correct / total,
        "macro_f1": sum(f1_values) / len(f1_values),
        "balanced_accuracy": sum(recalls) / len(recalls),
        "coverage": covered / total,
        "abstention_rate": 1 - covered / total,
        "selective_accuracy": covered_correct / covered if covered else 0.0,
        "paired_decision_loss": loss / total,
        "fatal_gate_count": fatal_count,
    }


def _empty_metrics() -> dict[str, float | int | str | bool]:
    return {
        "total": 0,
        "accuracy": 0.0,
        "macro_f1": 0.0,
        "balanced_accuracy": 0.0,
        "coverage": 0.0,
        "abstention_rate": 1.0,
        "selective_accuracy": 0.0,
        "paired_decision_loss": 0.0,
        "fatal_gate_count": 0,
    }


def _outcome_totals(
    predictions: Sequence[Prediction], targets: Mapping[str, DecisionLabel]
) -> tuple[int, int, int, float]:
    correct = covered = covered_correct = 0
    loss = 0.0
    for prediction in predictions:
        target = targets[prediction.case_id]
        is_correct = prediction.predicted_label == target
        correct += int(is_correct)
        if prediction.abstained:
            loss += 0.5
            continue
        covered += 1
        covered_correct += int(is_correct)
        loss += 0.0 if is_correct else 1.0
    return correct, covered, covered_correct, loss


def _class_metrics(
    predictions: Sequence[Prediction],
    targets: Mapping[str, DecisionLabel],
    labels: Sequence[DecisionLabel],
) -> tuple[list[float], list[float]]:
    f1_values: list[float] = []
    recalls: list[float] = []
    for label in labels:
        true_positive = sum(
            item.predicted_label == label and targets[item.case_id] == label for item in predictions
        )
        false_positive = sum(
            item.predicted_label == label and targets[item.case_id] != label for item in predictions
        )
        false_negative = sum(
            item.predicted_label != label and targets[item.case_id] == label for item in predictions
        )
        f1_denominator = 2 * true_positive + false_positive + false_negative
        recall_denominator = true_positive + false_negative
        f1_values.append(2 * true_positive / f1_denominator if f1_denominator else 0.0)
        recalls.append(true_positive / recall_denominator if recall_denominator else 0.0)
    return f1_values, recalls
