from __future__ import annotations

from ynoy.models.formal_comparison import (
    CaseClusterBinding,
    ComparisonSpec,
    ShiftStratumRequirement,
)
from ynoy.util import canonical_sha256

CASE_IDS = ("case-1", "case-2", "case-3", "case-4", "case-5", "case-6")
CLUSTERS = (
    CaseClusterBinding(case_id="case-1", cluster_id="cluster-a"),
    CaseClusterBinding(case_id="case-2", cluster_id="cluster-a"),
    CaseClusterBinding(case_id="case-3", cluster_id="cluster-a"),
    CaseClusterBinding(case_id="case-4", cluster_id="cluster-b"),
    CaseClusterBinding(case_id="case-5", cluster_id="cluster-c"),
    CaseClusterBinding(case_id="case-6", cluster_id="cluster-c"),
)


def comparison_spec(**updates) -> ComparisonSpec:
    payload = {
        "version": "comparison/1",
        "case_ids": CASE_IDS,
        "case_tie_order": tuple(reversed(CASE_IDS)),
        "cluster_bindings": CLUSTERS,
        "dependency_manifest_sha256": "1" * 64,
        "primary_baseline_id": "static-profile/1",
        "baseline_manifest_sha256": "2" * 64,
        "selector_version": "matched-coverage/1",
        "coverage_grid": (0.5, 1.0),
        "primary_coverage": 0.5,
        "rounding_tolerance": 1e-9,
        "minimum_case_support": 2,
        "minimum_cluster_support": 2,
        "risk_estimand": "case_weighted",
        "decision_rule": "primary_only",
        "minimum_effect": 0.05,
        "primary_risk_ceiling": 0.4,
        "bootstrap_seed": 17,
        "bootstrap_resamples": 200,
        "bootstrap_alpha": 0.05,
        "required_strata": (
            ShiftStratumRequirement(
                stratum="chronological_future",
                minimum_cases=1,
                minimum_clusters=1,
                absolute_risk_ceiling=0.5,
            ),
            ShiftStratumRequirement(
                stratum="high_risk",
                minimum_cases=1,
                minimum_clusters=1,
                absolute_risk_ceiling=0.2,
            ),
        ),
        **updates,
    }
    draft = ComparisonSpec.model_construct(**payload, spec_sha256="0" * 64)
    payload = draft.model_dump(mode="python")
    payload["spec_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"spec_sha256"})
    )
    return ComparisonSpec.model_validate(payload)


def scores(*, reverse: bool = False) -> dict[str, float]:
    items = (
        ("case-1", 0.9),
        ("case-2", 0.7),
        ("case-3", 0.7),
        ("case-4", 0.85),
        ("case-5", 0.8),
        ("case-6", 0.5),
    )
    return dict(reversed(items) if reverse else items)
