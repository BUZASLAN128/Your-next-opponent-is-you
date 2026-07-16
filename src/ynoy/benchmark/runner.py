from __future__ import annotations

from collections.abc import Sequence

from ynoy.benchmark.metrics import calculate_metrics
from ynoy.benchmark.predictors import build_predictor_input, predict_case
from ynoy.benchmark.protocol import evaluate_fatal_gates, verify_benchmark_manifest
from ynoy.errors import DataValidationError
from ynoy.models import (
    BenchmarkCase,
    BenchmarkManifest,
    BenchmarkPredictorInput,
    BenchmarkRun,
    DecisionLabel,
    EvidenceRegime,
    Prediction,
)
from ynoy.util import canonical_sha256


def run_benchmark(manifest: BenchmarkManifest, cases: Sequence[BenchmarkCase]) -> BenchmarkRun:
    verify_benchmark_manifest(manifest, cases)
    by_id = {case.case_id: case for case in cases}
    development = [by_id[case_id] for case_id in manifest.development_case_ids]
    sealed = [by_id[case_id] for case_id in manifest.sealed_case_ids]
    training_labels = [case.hidden_target for case in development]
    targets = {case.case_id: case.hidden_target for case in sealed}
    predictions: list[Prediction] = []
    metric_groups: dict[str, dict[str, float | int | str | bool]] = {}
    for regime in manifest.regimes:
        for algorithm in manifest.algorithms:
            group = [
                _predict_with_gates(
                    build_predictor_input(case),
                    case=case,
                    algorithm=algorithm,
                    regime=regime,
                    training_labels=training_labels,
                )
                for case in sealed
            ]
            predictions.extend(group)
            metric_groups[f"{regime.value}/{algorithm}"] = calculate_metrics(group, targets)
    challenge_gates = tuple(sorted({gate for case in cases for gate in evaluate_fatal_gates(case)}))
    return _build_run(manifest, predictions, metric_groups, fatal_gates=challenge_gates)


def _predict_with_gates(
    predictor_input: BenchmarkPredictorInput,
    *,
    case: BenchmarkCase,
    algorithm: str,
    regime: EvidenceRegime,
    training_labels: Sequence[DecisionLabel],
) -> Prediction:
    prediction = predict_case(
        predictor_input,
        algorithm=algorithm,
        regime=regime,
        training_labels=training_labels,
    )
    gates = evaluate_fatal_gates(case, prediction)
    return prediction.model_copy(update={"fatal_gate": gates[0] if gates else None})


def _build_run(
    manifest: BenchmarkManifest,
    predictions: list[Prediction],
    metrics: dict[str, dict[str, float | int | str | bool]],
    *,
    fatal_gates: tuple[str, ...] = (),
) -> BenchmarkRun:
    detected_gates = tuple(sorted({item.fatal_gate for item in predictions if item.fatal_gate}))
    fatal_gates = tuple(sorted(set(fatal_gates) | set(detected_gates)))
    draft = BenchmarkRun(
        manifest_id=manifest.record_id,
        manifest_sha256=manifest.manifest_sha256,
        status="invalid" if fatal_gates else "complete",
        predictions=tuple(predictions),
        metrics=metrics,
        fatal_gates=fatal_gates,
        acceptance_status="failed_fatal_gate" if fatal_gates else "not_calibrated",
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"run_sha256"}))
    return draft.model_copy(update={"run_sha256": digest})


def verify_benchmark_run(run: BenchmarkRun) -> None:
    expected = canonical_sha256(run.model_dump(mode="json", exclude={"run_sha256"}))
    if run.run_sha256 != expected:
        raise DataValidationError(
            "benchmark_run_digest_mismatch", "Benchmark run integrity check failed."
        )
