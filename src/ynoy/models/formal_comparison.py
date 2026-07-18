from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.util import canonical_sha256

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class CaseClusterBinding(StrictModel):
    case_id: str = Field(min_length=1)
    cluster_id: str = Field(min_length=1)


class ShiftStratumRequirement(StrictModel):
    stratum: str = Field(min_length=1)
    minimum_cases: int = Field(ge=1)
    minimum_clusters: int = Field(ge=1)
    absolute_risk_ceiling: float = Field(ge=0.0, le=1.0)


class ComparisonSpec(StrictModel):
    version: str = Field(min_length=1)
    case_ids: tuple[str, ...] = Field(min_length=1)
    case_tie_order: tuple[str, ...] = Field(min_length=1)
    cluster_bindings: tuple[CaseClusterBinding, ...] = Field(min_length=1)
    dependency_manifest_sha256: Sha256Digest
    primary_baseline_id: str = Field(min_length=1)
    baseline_manifest_sha256: Sha256Digest
    selector_version: str = Field(min_length=1)
    coverage_grid: tuple[float, ...] = Field(min_length=1)
    primary_coverage: float = Field(gt=0.0, le=1.0)
    rounding_tolerance: float = Field(ge=0.0, lt=0.5)
    minimum_case_support: int = Field(ge=1)
    minimum_cluster_support: int = Field(ge=1)
    risk_estimand: Literal["case_weighted", "cluster_weighted"]
    decision_rule: Literal["primary_only", "familywise_grid"]
    minimum_effect: float = Field(ge=0.0, le=1.0)
    primary_risk_ceiling: float = Field(ge=0.0, le=1.0)
    bootstrap_seed: int = Field(ge=0)
    bootstrap_resamples: int = Field(ge=100)
    bootstrap_alpha: float = Field(gt=0.0, lt=1.0)
    required_strata: tuple[ShiftStratumRequirement, ...] = Field(min_length=1)
    spec_sha256: Sha256Digest

    @model_validator(mode="after")
    def spec_is_frozen_and_total(self) -> ComparisonSpec:
        if self.case_ids != tuple(sorted(set(self.case_ids))):
            raise ValueError("comparison cases must be sorted and unique")
        if set(self.case_tie_order) != set(self.case_ids) or len(self.case_tie_order) != len(
            self.case_ids
        ):
            raise ValueError("tie order must be a permutation of frozen cases")
        bound_cases = tuple(item.case_id for item in self.cluster_bindings)
        if bound_cases != self.case_ids:
            raise ValueError("cluster manifest must bind every frozen case exactly once")
        if self.coverage_grid != tuple(sorted(set(self.coverage_grid))):
            raise ValueError("coverage grid must be sorted and unique")
        if any(value <= 0.0 or value > 1.0 for value in self.coverage_grid):
            raise ValueError("coverage values must be in (0, 1]")
        if self.primary_coverage not in self.coverage_grid:
            raise ValueError("primary coverage must be frozen in the coverage grid")
        strata = tuple(item.stratum for item in self.required_strata)
        if strata != tuple(sorted(set(strata))):
            raise ValueError("required shift strata must be sorted and unique")
        identifiers = (
            self.version,
            self.primary_baseline_id,
            self.selector_version,
            *self.case_ids,
            *self.case_tie_order,
            *strata,
        )
        if any(item != item.strip() for item in identifiers):
            raise ValueError("comparison identifiers must be trimmed")
        payload = self.model_dump(mode="json", exclude={"spec_sha256"})
        if self.spec_sha256 != canonical_sha256(payload):
            raise ValueError("comparison spec hash does not match its payload")
        return self


class MatchedCoverageSelection(StrictModel):
    coverage: float = Field(gt=0.0, le=1.0)
    available: bool
    ynoy_case_ids: tuple[str, ...] = ()
    baseline_case_ids: tuple[str, ...] = ()
    ynoy_cluster_count: int = Field(ge=0)
    baseline_cluster_count: int = Field(ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def availability_is_consistent(self) -> MatchedCoverageSelection:
        populated = bool(self.ynoy_case_ids and self.baseline_case_ids)
        if self.available != (populated and self.reason is None):
            raise ValueError("matched selection availability is inconsistent")
        return self


class RiskEstimate(StrictModel):
    estimand: Literal["case_weighted", "cluster_weighted"]
    value: float = Field(ge=0.0, le=1.0)
    case_count: int = Field(ge=1)
    cluster_count: int = Field(ge=1)


class CoverageInference(StrictModel):
    coverage: float = Field(gt=0.0, le=1.0)
    interval_rule: Literal["pointwise", "simultaneous", "familywise"]
    ynoy_risk_upper: float = Field(ge=0.0, le=1.0)
    risk_difference_upper: float = Field(ge=-1.0, le=1.0)


class StratumInference(StrictModel):
    stratum: str = Field(min_length=1)
    case_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    simultaneous_risk_upper: float = Field(ge=0.0, le=1.0)


class ComparisonDecision(StrictModel):
    status: Literal["win", "not_win", "inconclusive"]
    primary_coverage: float = Field(gt=0.0, le=1.0)
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def reasons_match_status(self) -> ComparisonDecision:
        if self.status == "win" and self.reasons:
            raise ValueError("winning comparison cannot carry failure reasons")
        if self.status != "win" and not self.reasons:
            raise ValueError("non-winning comparison requires a reason")
        return self
