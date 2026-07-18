from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import ValidationError

from ynoy.models.formal_comparison import (
    ComparisonDecision,
    ComparisonSpec,
    CoverageInference,
    MatchedCoverageSelection,
    RiskEstimate,
    StratumInference,
)


def select_matched_coverage(
    spec: ComparisonSpec,
    *,
    ynoy_scores: Mapping[str, float],
    baseline_scores: Mapping[str, float],
    coverage: float,
) -> MatchedCoverageSelection:
    checked = _validated_spec(spec)
    if checked is None:
        return _unavailable(coverage, "invalid_comparison_spec")
    if coverage not in checked.coverage_grid:
        return _unavailable(coverage, "coverage_not_frozen")
    if not _scores_are_valid(checked, ynoy_scores, baseline_scores):
        return _unavailable(coverage, "score_manifest_mismatch")
    raw_count = len(checked.case_ids) * coverage
    selected_count = round(raw_count)
    if selected_count < 1 or abs(raw_count - selected_count) > checked.rounding_tolerance:
        return _unavailable(coverage, "unsupported_coverage_count")
    ynoy = _top_cases(checked, ynoy_scores, selected_count)
    baseline = _top_cases(checked, baseline_scores, selected_count)
    ynoy_clusters = _cluster_count(checked, ynoy)
    baseline_clusters = _cluster_count(checked, baseline)
    if (
        selected_count < checked.minimum_case_support
        or min(ynoy_clusters, baseline_clusters) < checked.minimum_cluster_support
    ):
        return _unavailable(coverage, "minimum_support_not_met")
    return MatchedCoverageSelection(
        coverage=coverage,
        available=True,
        ynoy_case_ids=ynoy,
        baseline_case_ids=baseline,
        ynoy_cluster_count=ynoy_clusters,
        baseline_cluster_count=baseline_clusters,
    )


def estimate_finite_risk(
    spec: ComparisonSpec,
    *,
    selected_case_ids: Sequence[str],
    losses: Mapping[str, float],
) -> RiskEstimate | None:
    checked = _validated_spec(spec)
    selected = tuple(selected_case_ids)
    if checked is None or not selected or len(set(selected)) != len(selected):
        return None
    if any(case_id not in checked.case_ids for case_id in selected):
        return None
    raw_values = tuple(losses.get(case_id) for case_id in selected)
    if any(
        value is None or not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in raw_values
    ):
        return None
    values = {case_id: losses[case_id] for case_id in selected}
    cluster_map = _cluster_map(checked)
    clusters = {cluster_map[case_id] for case_id in selected}
    value = _risk_value(checked.risk_estimand, selected, values, cluster_map)
    return RiskEstimate(
        estimand=checked.risk_estimand,
        value=value,
        case_count=len(selected),
        cluster_count=len(clusters),
    )


def paired_cluster_bootstrap_upper(
    spec: ComparisonSpec,
    *,
    paired_loss_differences: Mapping[str, float],
) -> float | None:
    checked = _validated_spec(spec)
    if checked is None or set(paired_loss_differences) != set(checked.case_ids):
        return None
    if any(
        not math.isfinite(value) or not -1.0 <= value <= 1.0
        for value in paired_loss_differences.values()
    ):
        return None
    grouped = _cluster_values(checked, paired_loss_differences)
    cluster_ids = tuple(sorted(grouped))
    generator = random.Random(checked.bootstrap_seed)
    samples = [
        _bootstrap_draw(generator, cluster_ids, grouped, checked.risk_estimand)
        for _ in range(checked.bootstrap_resamples)
    ]
    samples.sort()
    index = min(len(samples) - 1, math.ceil((1.0 - checked.bootstrap_alpha) * len(samples)) - 1)
    return samples[index]


def evaluate_comparison(
    spec: ComparisonSpec,
    *,
    selection: MatchedCoverageSelection,
    coverage_inferences: Mapping[float, CoverageInference],
    stratum_inferences: Sequence[StratumInference],
) -> ComparisonDecision:
    checked = _validated_spec(spec)
    if checked is None:
        return _decision(spec.primary_coverage, "inconclusive", "invalid_comparison_spec")
    if not selection.available or selection.coverage != checked.primary_coverage:
        return _decision(checked.primary_coverage, "inconclusive", "primary_coverage_unavailable")
    primary = coverage_inferences.get(checked.primary_coverage)
    if primary is None:
        return _decision(checked.primary_coverage, "inconclusive", "primary_inference_missing")
    if checked.decision_rule == "familywise_grid" and primary.interval_rule not in {
        "simultaneous",
        "familywise",
    }:
        return _decision(checked.primary_coverage, "inconclusive", "familywise_evidence_missing")
    strata_status = _evaluate_strata(checked, stratum_inferences)
    if strata_status is not None:
        return strata_status
    if primary.ynoy_risk_upper > checked.primary_risk_ceiling:
        return _decision(checked.primary_coverage, "not_win", "primary_risk_ceiling_failed")
    if primary.risk_difference_upper > -checked.minimum_effect:
        return _decision(checked.primary_coverage, "not_win", "minimum_effect_not_met")
    return ComparisonDecision(status="win", primary_coverage=checked.primary_coverage, reasons=())


def _evaluate_strata(
    spec: ComparisonSpec,
    evidence: Sequence[StratumInference],
) -> ComparisonDecision | None:
    by_name = {item.stratum: item for item in evidence}
    if len(by_name) != len(evidence):
        return _decision(spec.primary_coverage, "inconclusive", "shift_stratum_duplicated")
    for requirement in spec.required_strata:
        observed = by_name.get(requirement.stratum)
        if observed is None:
            return _decision(
                spec.primary_coverage, "inconclusive", "required_shift_stratum_missing"
            )
        if observed.case_count < requirement.minimum_cases or observed.cluster_count < (
            requirement.minimum_clusters
        ):
            return _decision(spec.primary_coverage, "inconclusive", "shift_stratum_support_low")
        if observed.simultaneous_risk_upper > requirement.absolute_risk_ceiling:
            return _decision(spec.primary_coverage, "not_win", "shift_stratum_risk_ceiling_failed")
    return None


def _validated_spec(spec: ComparisonSpec) -> ComparisonSpec | None:
    try:
        return ComparisonSpec.model_validate(spec.model_dump(mode="python"))
    except ValidationError:
        return None


def _scores_are_valid(spec: ComparisonSpec, *scores: Mapping[str, float]) -> bool:
    return all(
        set(items) == set(spec.case_ids)
        and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in items.values())
        for items in scores
    )


def _top_cases(spec: ComparisonSpec, scores: Mapping[str, float], count: int) -> tuple[str, ...]:
    tie_rank = {case_id: index for index, case_id in enumerate(spec.case_tie_order)}
    return tuple(sorted(spec.case_ids, key=lambda item: (-scores[item], tie_rank[item]))[:count])


def _cluster_map(spec: ComparisonSpec) -> dict[str, str]:
    return {item.case_id: item.cluster_id for item in spec.cluster_bindings}


def _cluster_count(spec: ComparisonSpec, case_ids: Sequence[str]) -> int:
    cluster_map = _cluster_map(spec)
    return len({cluster_map[item] for item in case_ids})


def _risk_value(
    estimand: Literal["case_weighted", "cluster_weighted"],
    selected: Sequence[str],
    values: Mapping[str, float],
    cluster_map: Mapping[str, str],
) -> float:
    if estimand == "case_weighted":
        return sum(values[item] for item in selected) / len(selected)
    clusters: dict[str, list[float]] = {}
    for case_id in selected:
        clusters.setdefault(cluster_map[case_id], []).append(values[case_id])
    means = tuple(sum(items) / len(items) for items in clusters.values())
    return sum(means) / len(means)


def _cluster_values(
    spec: ComparisonSpec,
    values: Mapping[str, float],
) -> dict[str, tuple[float, ...]]:
    grouped: dict[str, list[float]] = {}
    for case_id, cluster_id in _cluster_map(spec).items():
        grouped.setdefault(cluster_id, []).append(values[case_id])
    return {key: tuple(items) for key, items in grouped.items()}


def _bootstrap_draw(
    generator: random.Random,
    cluster_ids: tuple[str, ...],
    grouped: Mapping[str, tuple[float, ...]],
    estimand: Literal["case_weighted", "cluster_weighted"],
) -> float:
    sampled = tuple(generator.choice(cluster_ids) for _ in cluster_ids)
    if estimand == "cluster_weighted":
        values = tuple(sum(grouped[item]) / len(grouped[item]) for item in sampled)
    else:
        values = tuple(value for item in sampled for value in grouped[item])
    return sum(values) / len(values)


def _unavailable(coverage: float, reason: str) -> MatchedCoverageSelection:
    return MatchedCoverageSelection(
        coverage=coverage,
        available=False,
        ynoy_cluster_count=0,
        baseline_cluster_count=0,
        reason=reason,
    )


def _decision(
    coverage: float,
    status: Literal["not_win", "inconclusive"],
    reason: str,
) -> ComparisonDecision:
    return ComparisonDecision(status=status, primary_coverage=coverage, reasons=(reason,))
