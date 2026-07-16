from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ynoy.errors import DataValidationError
from ynoy.models import (
    BenchmarkCase,
    BenchmarkPredictorInput,
    DecisionLabel,
    EvidenceRegime,
    Prediction,
)


@dataclass(frozen=True, slots=True)
class PredictedValue:
    label: DecisionLabel
    receipts: tuple[str, ...] = ()


def label_markers(values: Sequence[str]) -> list[DecisionLabel]:
    labels: list[DecisionLabel] = []
    for value in values:
        normalized = value.casefold()
        for label in DecisionLabel:
            marker = rf"\bdecision\s*:\s*{re.escape(label.value)}\b"
            if re.search(marker, normalized):
                labels.append(label)
    return labels


def majority(labels: Sequence[DecisionLabel]) -> DecisionLabel:
    if not labels:
        return DecisionLabel.UNKNOWN
    counts = Counter(labels)
    return sorted(counts, key=lambda label: (-counts[label], label.value))[0]


def build_predictor_input(case: BenchmarkCase) -> BenchmarkPredictorInput:
    """Copy only fields a predictor may observe; sealed targets never cross this boundary."""
    return BenchmarkPredictorInput(
        case_id=case.case_id,
        domain=case.domain,
        task_type=case.task_type,
        decision_class=case.decision_class,
        event_time=case.event_time,
        dependency_cluster_id=case.dependency_cluster_id,
        task_context=case.task_context,
        evidence=case.evidence,
        declared_profile=case.declared_profile,
        structured_core=case.structured_core,
        data_class=case.data_class,
        synthetic=case.synthetic,
        challenge_tags=case.challenge_tags,
    )


def available_fields(
    case: BenchmarkPredictorInput, regime: EvidenceRegime
) -> dict[str, tuple[str, ...]]:
    if regime == EvidenceRegime.ZERO:
        return {"evidence": (), "declared": (), "core": ()}
    if regime == EvidenceRegime.DECLARED:
        return {"evidence": (), "declared": case.declared_profile, "core": ()}
    if regime == EvidenceRegime.LOW:
        return {
            "evidence": case.evidence[: min(3, len(case.evidence))],
            "declared": case.declared_profile,
            "core": (),
        }
    return {
        "evidence": case.evidence,
        "declared": case.declared_profile,
        "core": case.structured_core,
    }


def lexical_best(task_context: str, values: Sequence[str]) -> str | None:
    task_tokens = set(re.findall(r"[\w-]+", task_context.casefold()))
    ranked = sorted(
        values,
        key=lambda value: (
            -len(task_tokens & set(re.findall(r"[\w-]+", value.casefold()))),
            value,
        ),
    )
    return ranked[0] if ranked else None


def predict_case(
    case: BenchmarkPredictorInput,
    *,
    algorithm: str,
    regime: EvidenceRegime,
    training_labels: Sequence[DecisionLabel],
) -> Prediction:
    if not isinstance(case, BenchmarkPredictorInput):
        raise DataValidationError(
            "benchmark_predictor_input_required",
            "Predictors accept only target-free benchmark inputs.",
        )
    fields = available_fields(case, regime)
    predictor = PREDICTORS.get(algorithm)
    if predictor is None:
        raise DataValidationError(
            "benchmark_algorithm_unknown", f"Unknown benchmark algorithm: {algorithm}."
        )
    result = predictor(case, fields, regime, training_labels)
    abstained = result.label == DecisionLabel.UNKNOWN
    return Prediction(
        case_id=case.case_id,
        algorithm=algorithm,
        regime=regime,
        predicted_label=result.label,
        confidence=0.0 if abstained else 0.7,
        abstained=abstained,
        evidence_receipts=result.receipts,
        unknowns=("represented_user_decision",) if abstained else (),
    )


Predictor = Callable[
    [
        BenchmarkPredictorInput,
        dict[str, tuple[str, ...]],
        EvidenceRegime,
        Sequence[DecisionLabel],
    ],
    PredictedValue,
]


def _no_personalization(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del case, fields
    label = DecisionLabel.UNKNOWN if regime == EvidenceRegime.ZERO else majority(training)
    return PredictedValue(label)


def _recent_context(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del regime, training
    values = fields["evidence"][-1:]
    receipts = (f"{case.case_id}:evidence:{len(fields['evidence']) - 1}",) if values else ()
    return PredictedValue(majority(label_markers(values)), receipts)


def _declared_profile(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del regime, training
    receipts = tuple(f"{case.case_id}:declared:{index}" for index in range(len(fields["declared"])))
    return PredictedValue(majority(label_markers(fields["declared"])), receipts)


def _static_summary(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del regime, training
    values = (*fields["declared"], *fields["evidence"])
    receipts = (f"{case.case_id}:summary",) if values else ()
    return PredictedValue(majority(label_markers(values)), receipts)


def _lexical_retrieval(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del regime, training
    best = lexical_best(case.task_context, fields["evidence"])
    receipts = (f"{case.case_id}:retrieval",) if best else ()
    return PredictedValue(
        majority(label_markers((best,))) if best else DecisionLabel.UNKNOWN, receipts
    )


def _frequency_profile(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del regime
    personal = label_markers((*fields["declared"], *fields["evidence"]))
    receipts = (f"{case.case_id}:frequency",) if personal else ()
    return PredictedValue(majority(personal or list(training)), receipts)


def _structured_core(
    case: BenchmarkPredictorInput,
    fields: dict[str, tuple[str, ...]],
    regime: EvidenceRegime,
    training: Sequence[DecisionLabel],
) -> PredictedValue:
    del regime, training
    receipts = tuple(f"{case.case_id}:core:{index}" for index in range(len(fields["core"])))
    return PredictedValue(majority(label_markers(fields["core"])), receipts)


PREDICTORS: dict[str, Predictor] = {
    "no_personalization": _no_personalization,
    "recent_context": _recent_context,
    "declared_profile": _declared_profile,
    "static_summary": _static_summary,
    "lexical_retrieval": _lexical_retrieval,
    "frequency_profile": _frequency_profile,
    "structured_core": _structured_core,
}
