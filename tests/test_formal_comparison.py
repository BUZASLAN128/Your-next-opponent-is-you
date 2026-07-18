from __future__ import annotations

import pytest
from support.formal_evaluation import CASE_IDS, comparison_spec, scores

from ynoy.formal_evaluation_runtime import (
    estimate_finite_risk,
    evaluate_comparison,
    paired_cluster_bootstrap_upper,
    select_matched_coverage,
)
from ynoy.models.formal_comparison import CoverageInference, StratumInference


def _selection(spec):
    return select_matched_coverage(
        spec,
        ynoy_scores=scores(),
        baseline_scores={case_id: 0.7 for case_id in CASE_IDS},
        coverage=spec.primary_coverage,
    )


def _primary(spec, *, difference: float = -0.1, rule: str = "pointwise"):
    return CoverageInference(
        coverage=spec.primary_coverage,
        interval_rule=rule,
        ynoy_risk_upper=0.3,
        risk_difference_upper=difference,
    )


def _strata(*, high_risk_upper: float = 0.15):
    return (
        StratumInference(
            stratum="chronological_future",
            case_count=2,
            cluster_count=2,
            simultaneous_risk_upper=0.4,
        ),
        StratumInference(
            stratum="high_risk",
            case_count=2,
            cluster_count=2,
            simultaneous_risk_upper=high_risk_upper,
        ),
    )


def test_minimum_coverage_blocks_easy_case_win() -> None:
    spec = comparison_spec(
        coverage_grid=(1 / 6, 0.5, 1.0),
        primary_coverage=1 / 6,
        minimum_case_support=2,
    )

    selection = _selection(spec)

    assert not selection.available and selection.reason == "minimum_support_not_met"


def test_matched_coverage_selector_is_deterministic_label_blind_and_tolerance_bound() -> None:
    spec = comparison_spec(coverage_grid=(0.4, 0.5, 1.0))
    first = select_matched_coverage(
        spec,
        ynoy_scores=scores(),
        baseline_scores=scores(reverse=True),
        coverage=0.5,
    )
    second = select_matched_coverage(
        spec,
        ynoy_scores=scores(reverse=True),
        baseline_scores=scores(),
        coverage=0.5,
    )
    unsupported = select_matched_coverage(
        spec,
        ynoy_scores=scores(),
        baseline_scores=scores(),
        coverage=0.4,
    )

    assert first == second
    assert not unsupported.available and unsupported.reason == "unsupported_coverage_count"


def test_matched_coverage_uses_frozen_finite_risk_estimand() -> None:
    losses = dict(zip(CASE_IDS, (0.0, 0.0, 0.0, 1.0, 1.0, 1.0), strict=True))
    case_spec = comparison_spec(risk_estimand="case_weighted")
    cluster_spec = comparison_spec(risk_estimand="cluster_weighted")

    case_risk = estimate_finite_risk(case_spec, selected_case_ids=CASE_IDS, losses=losses)
    cluster_risk = estimate_finite_risk(cluster_spec, selected_case_ids=CASE_IDS, losses=losses)
    rebound = case_spec.model_copy(update={"risk_estimand": "cluster_weighted"})

    assert case_risk is not None and case_risk.value == pytest.approx(0.5)
    assert cluster_risk is not None and cluster_risk.value == pytest.approx(2 / 3)
    assert estimate_finite_risk(rebound, selected_case_ids=CASE_IDS, losses=losses) is None
    assert estimate_finite_risk(case_spec, selected_case_ids=(), losses=losses) is None


def test_baseline_and_cluster_manifest_cannot_change_after_freeze() -> None:
    spec = comparison_spec()
    mutations = (
        spec.model_copy(update={"primary_baseline_id": "posthoc-baseline"}),
        spec.model_copy(update={"cluster_bindings": tuple(reversed(spec.cluster_bindings))}),
        spec.model_copy(update={"selector_version": "posthoc-selector"}),
    )

    for rebound in mutations:
        selection = select_matched_coverage(
            rebound,
            ynoy_scores=scores(),
            baseline_scores=scores(),
            coverage=0.5,
        )
        assert not selection.available and selection.reason == "invalid_comparison_spec"


def test_posthoc_coverage_selection_cannot_win() -> None:
    spec = comparison_spec()
    inferences = {
        0.5: _primary(spec, difference=0.0),
        1.0: CoverageInference(
            coverage=1.0,
            interval_rule="pointwise",
            ynoy_risk_upper=0.2,
            risk_difference_upper=-0.2,
        ),
    }

    decision = evaluate_comparison(
        spec,
        selection=_selection(spec),
        coverage_inferences=inferences,
        stratum_inferences=_strata(),
    )

    assert decision.status == "not_win" and decision.reasons == ("minimum_effect_not_met",)


def test_pointwise_intervals_do_not_satisfy_familywise_rule() -> None:
    spec = comparison_spec(decision_rule="familywise_grid")

    decision = evaluate_comparison(
        spec,
        selection=_selection(spec),
        coverage_inferences={0.5: _primary(spec, rule="pointwise")},
        stratum_inferences=_strata(),
    )

    assert decision.status == "inconclusive"
    assert decision.reasons == ("familywise_evidence_missing",)


def test_missing_required_shift_stratum_is_inconclusive() -> None:
    spec = comparison_spec()

    decision = evaluate_comparison(
        spec,
        selection=_selection(spec),
        coverage_inferences={0.5: _primary(spec)},
        stratum_inferences=_strata()[:1],
    )

    assert decision.status == "inconclusive"
    assert decision.reasons == ("required_shift_stratum_missing",)


def test_supported_high_risk_stratum_cannot_be_hidden_by_pooling() -> None:
    spec = comparison_spec()

    decision = evaluate_comparison(
        spec,
        selection=_selection(spec),
        coverage_inferences={0.5: _primary(spec)},
        stratum_inferences=_strata(high_risk_upper=0.25),
    )

    assert decision.status == "not_win"
    assert decision.reasons == ("shift_stratum_risk_ceiling_failed",)


def test_paired_cluster_bootstrap_is_seeded_by_frozen_spec() -> None:
    spec = comparison_spec()
    differences = dict(zip(CASE_IDS, (-0.1, -0.2, -0.1, 0.0, -0.3, -0.2), strict=True))

    first = paired_cluster_bootstrap_upper(spec, paired_loss_differences=differences)
    second = paired_cluster_bootstrap_upper(spec, paired_loss_differences=differences)

    assert first == second and first is not None
