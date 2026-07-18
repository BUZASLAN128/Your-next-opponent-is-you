from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.formal_decision import DecisionGroupKey
from ynoy.util import canonical_sha256

type Sha256Digest = str


class CalibrationBin(StrictModel):
    lower_score: float = Field(ge=0.0, le=1.0)
    upper_score: float = Field(ge=0.0, le=1.0)
    calibrated_probability: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def interval_is_valid(self) -> CalibrationBin:
        if self.upper_score < self.lower_score:
            raise ValueError("calibration bin upper score cannot precede lower score")
        return self


class CalibrationProfile(StrictModel):
    requested_output: str = Field(min_length=1)
    full_decision_target: DecisionGroupKey
    represented_user_outcome: str = Field(min_length=1)
    basis: Literal["inferredPersona"] = "inferredPersona"
    predictor_version: str = Field(min_length=1)
    extractor_version: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    mapping_version: str = Field(min_length=1)
    strata: tuple[str, ...] = Field(min_length=1)
    fit_case_ids: tuple[str, ...] = Field(min_length=1)
    validation_case_ids: tuple[str, ...] = Field(min_length=1)
    sealed_case_ids: tuple[str, ...] = Field(min_length=1)
    bins: tuple[CalibrationBin, ...] = Field(min_length=1)
    persona_threshold: float = Field(ge=0.0, le=1.0)
    freeze_receipt_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")
    profile_sha256: Sha256Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_is_frozen_and_disjoint(self) -> CalibrationProfile:
        identifiers = (
            self.requested_output,
            self.represented_user_outcome,
            self.predictor_version,
            self.extractor_version,
            self.feature_schema_version,
            self.mapping_version,
            *self.strata,
        )
        if any(value != value.strip() for value in identifiers):
            raise ValueError("calibration profile identifiers must be trimmed")
        partitions = (
            set(self.fit_case_ids),
            set(self.validation_case_ids),
            set(self.sealed_case_ids),
        )
        if any(
            left & right
            for index, left in enumerate(partitions)
            for right in partitions[index + 1 :]
        ):
            raise ValueError("calibration partitions must be disjoint")
        if any(
            len(values) != len(set(values))
            for values in (
                self.fit_case_ids,
                self.validation_case_ids,
                self.sealed_case_ids,
                self.strata,
            )
        ):
            raise ValueError("calibration profile identifiers must be unique")
        ordered = tuple(sorted(self.bins, key=lambda item: (item.lower_score, item.upper_score)))
        if ordered != self.bins or any(
            left.upper_score >= right.lower_score
            for left, right in zip(self.bins, self.bins[1:], strict=False)
        ):
            raise ValueError("calibration bins must be ordered and non-overlapping")
        payload = self.model_dump(mode="json", exclude={"profile_sha256"})
        if self.profile_sha256 != canonical_sha256(payload):
            raise ValueError("calibration profile hash does not match its payload")
        return self

    def probability_for(self, ranking_score: float) -> float | None:
        for item in self.bins:
            if item.lower_score <= ranking_score <= item.upper_score:
                return item.calibrated_probability
        return None
