from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from conftest import benchmark_cases

from ynoy.benchmark import (
    freeze_benchmark,
    load_benchmark_cases,
    run_benchmark,
    verify_benchmark_run,
)
from ynoy.benchmark.predictors import build_predictor_input, predict_case
from ynoy.benchmark.protocol import (
    FATAL_GATES,
    evaluate_fatal_gates,
    split_dependency_clusters,
    verify_benchmark_manifest,
)
from ynoy.errors import DataValidationError
from ynoy.models import (
    BenchmarkManifest,
    BenchmarkPredictorInput,
    DecisionLabel,
    EvidenceRegime,
)
from ynoy.report import render_benchmark_markdown
from ynoy.util import canonical_sha256


def _reseal_manifest(manifest: BenchmarkManifest, **updates: object) -> BenchmarkManifest:
    """Return a semantically changed manifest with its outer hash resealed."""
    draft = manifest.model_copy(update=updates)
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"manifest_sha256"}))
    return draft.model_copy(update={"manifest_sha256": digest})


def test_freeze_separates_dependency_clusters_and_seals_manifest() -> None:
    cases = benchmark_cases()
    development, sealed, cutoff = split_dependency_clusters(cases, development_fraction=0.5)
    development_clusters = {case.dependency_cluster_id for case in development}
    sealed_clusters = {case.dependency_cluster_id for case in sealed}
    assert development_clusters.isdisjoint(sealed_clusters)
    assert cutoff == max(case.event_time for case in development)
    manifest = freeze_benchmark("coding-pilot", cases, development_fraction=0.5)
    assert manifest.sealed is True
    assert set(manifest.development_case_ids).isdisjoint(manifest.sealed_case_ids)
    assert set(manifest.case_ids) == {
        *manifest.development_case_ids,
        *manifest.sealed_case_ids,
    }
    verify_benchmark_manifest(manifest, cases)


def test_interleaved_dependency_clusters_fail_closed_temporal_holdout() -> None:
    cases = benchmark_cases()
    interleaved = [
        case.model_copy(
            update={
                "dependency_cluster_id": "cluster-a" if index % 2 == 0 else "cluster-b",
                "event_time": cases[0].event_time + timedelta(days=index),
            }
        )
        for index, case in enumerate(cases)
    ]

    with pytest.raises(DataValidationError):
        split_dependency_clusters(interleaved, development_fraction=0.5)


@pytest.mark.parametrize(
    "updates",
    [
        pytest.param({"protocol_sha256": "0" * 64}, id="protocol"),
        pytest.param({"algorithms": ("no_personalization",)}, id="algorithms"),
        pytest.param({"regimes": (EvidenceRegime.ZERO,)}, id="regimes"),
        pytest.param({"development_case_ids": ()}, id="partition"),
        pytest.param(
            {"temporal_cutoff": benchmark_cases()[0].event_time + timedelta(days=100)},
            id="cutoff",
        ),
    ],
)
def test_manifest_semantic_tampering_is_rejected_after_outer_hash_reseal(
    updates: dict[str, object],
) -> None:
    cases = benchmark_cases()
    manifest = freeze_benchmark("coding-pilot", cases, development_fraction=0.5)
    tampered = _reseal_manifest(manifest, **updates)

    with pytest.raises(DataValidationError):
        verify_benchmark_manifest(tampered, cases)


def test_manifest_integrity_rejects_metadata_or_case_changes() -> None:
    cases = benchmark_cases()
    manifest = freeze_benchmark("coding-pilot", cases, development_fraction=0.5)
    tampered_manifest = manifest.model_copy(update={"name": "changed-after-freeze"})
    with pytest.raises(DataValidationError) as manifest_error:
        verify_benchmark_manifest(tampered_manifest, cases)
    assert manifest_error.value.code == "benchmark_manifest_digest_mismatch"
    changed_cases = list(cases)
    changed_cases[0] = changed_cases[0].model_copy(update={"task_context": "changed after freeze"})
    with pytest.raises(DataValidationError) as case_error:
        verify_benchmark_manifest(manifest, changed_cases)
    assert case_error.value.code == "benchmark_case_set_changed"


def test_hidden_target_never_changes_predictor_input_result() -> None:
    case = benchmark_cases()[0]
    opposite = case.model_copy(
        update={
            "hidden_target": DecisionLabel.REJECT,
            "hidden_rationale_terms": ("sealed", "changed"),
        }
    )
    first_input = build_predictor_input(case)
    second_input = build_predictor_input(opposite)
    assert first_input == second_input
    assert not hasattr(first_input, "hidden_target")
    assert not hasattr(first_input, "hidden_rationale_terms")
    assert "hidden_target" not in first_input.model_dump(mode="json")
    assert "hidden_rationale_terms" not in first_input.model_dump(mode="json")
    first = predict_case(
        first_input,
        algorithm="structured_core",
        regime=EvidenceRegime.HISTORY_RICH,
        training_labels=(DecisionLabel.ACCEPT,),
    )
    second = predict_case(
        second_input,
        algorithm="structured_core",
        regime=EvidenceRegime.HISTORY_RICH,
        training_labels=(DecisionLabel.ACCEPT,),
    )
    assert first == second


def test_predictor_rejects_direct_benchmark_case_input() -> None:
    case = cast(BenchmarkPredictorInput, benchmark_cases()[0])
    with pytest.raises(DataValidationError) as blocked:
        predict_case(
            case,
            algorithm="no_personalization",
            regime=EvidenceRegime.ZERO,
            training_labels=(),
        )
    assert blocked.value.code == "benchmark_predictor_input_required"


def test_benchmark_fixture_support_does_not_echo_each_hidden_target() -> None:
    for case in benchmark_cases():
        marker = f"decision:{case.hidden_target.value}"
        support_channels = (case.evidence, case.declared_profile, case.structured_core)
        assert all(marker not in " ".join(channel).casefold() for channel in support_channels)


def test_zero_regime_exposes_no_personal_evidence() -> None:
    case = build_predictor_input(benchmark_cases()[0])
    for algorithm in (
        "recent_context",
        "declared_profile",
        "static_summary",
        "lexical_retrieval",
        "structured_core",
    ):
        prediction = predict_case(
            case,
            algorithm=algorithm,
            regime=EvidenceRegime.ZERO,
            training_labels=(),
        )
        assert prediction.predicted_label == DecisionLabel.UNKNOWN
        assert prediction.evidence_receipts == ()
        assert prediction.abstained is True


def test_benchmark_run_reports_metrics_without_claiming_calibration() -> None:
    cases = benchmark_cases()
    manifest = freeze_benchmark("coding-pilot", cases, development_fraction=0.5)
    run = run_benchmark(manifest, cases)
    sealed_count = len(manifest.sealed_case_ids)
    assert len(run.predictions) == sealed_count * len(manifest.algorithms) * len(manifest.regimes)
    assert run.status == "complete"
    assert run.acceptance_status == "not_calibrated"
    assert run.local_only is True and run.external_calls == ()
    assert run.fatal_gates == ()
    assert all(int(metrics["total"]) == sealed_count for metrics in run.metrics.values())
    assert all(0.0 <= float(metrics["macro_f1"]) <= 1.0 for metrics in run.metrics.values())
    verify_benchmark_run(run)
    report = render_benchmark_markdown(manifest, run)
    assert "Synthetic protocol/implementation check".casefold() in report.casefold()
    assert "No real acceptance threshold is claimed" in report
    assert "no action authority" in report


def test_explicit_fatal_challenge_tag_invalidates_benchmark_run() -> None:
    cases = benchmark_cases()
    cases[0] = cases[0].model_copy(update={"challenge_tags": (FATAL_GATES[0],)})
    manifest = freeze_benchmark("coding-pilot", cases, development_fraction=0.5)

    run = run_benchmark(manifest, cases)

    assert evaluate_fatal_gates(cases[0], run.predictions[0]) == (FATAL_GATES[0],)
    assert run.status == "invalid"
    assert run.fatal_gates == (FATAL_GATES[0],)
    assert run.acceptance_status == "failed_fatal_gate"


def test_benchmark_run_integrity_rejects_metric_tampering() -> None:
    cases = benchmark_cases()
    manifest = freeze_benchmark("coding-pilot", cases, development_fraction=0.5)
    run = run_benchmark(manifest, cases)
    changed = run.model_copy(update={"metrics": {}})
    with pytest.raises(DataValidationError) as error:
        verify_benchmark_run(changed)
    assert error.value.code == "benchmark_run_digest_mismatch"


def test_case_loader_requires_multiple_dependency_clusters(tmp_path: Path) -> None:
    raw = [case.model_dump(mode="json") for case in benchmark_cases()[:2]]
    for item in raw:
        item["dependency_cluster_id"] = "same-cluster"
    source = tmp_path / "cases.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DataValidationError) as error:
        load_benchmark_cases(source)
    assert error.value.code == "benchmark_clusters_insufficient"
