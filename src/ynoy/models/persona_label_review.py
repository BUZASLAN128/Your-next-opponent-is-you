from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_labels import PersonaAnnotationJudgment
from ynoy.util import canonical_sha256


class RepeatPairAgreement(StrictModel):
    window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_presentation_ids: tuple[str, str]
    matching_fields: tuple[str, ...]
    mismatching_fields: tuple[str, ...]
    exact_match: bool

    @model_validator(mode="after")
    def match_flag_is_consistent(self) -> RepeatPairAgreement:
        if self.exact_match != (not self.mismatching_fields):
            raise ValueError("repeat agreement flag contradicts its mismatching fields")
        if set(self.matching_fields) & set(self.mismatching_fields):
            raise ValueError("repeat agreement fields must be disjoint")
        return self


class PersonaInitialLabelReceipt(StrictModel):
    protocol_version: Literal["persona-label-initial/0.1"] = "persona-label-initial/0.1"
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    label_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    presentation_count: Literal[32] = 32
    unique_window_count: Literal[24] = 24
    repeat_pair_count: Literal[8] = 8
    repeat_exact_match_count: int = Field(ge=0, le=8)
    repeat_mismatch_count: int = Field(ge=0, le=8)
    field_agreement_counts: dict[str, int]
    pair_results: tuple[RepeatPairAgreement, ...] = Field(min_length=8, max_length=8)
    adjudication_required: bool
    interpretation_authority: Literal["represented_user_local_attestation"] = (
        "represented_user_local_attestation"
    )
    identity_authentication: Literal["local_operator_attestation_not_cryptographic"] = (
        "local_operator_attestation_not_cryptographic"
    )
    persona_quality_claimed: Literal[False] = False
    protected_holdout_used: Literal[False] = False
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> PersonaInitialLabelReceipt:
        if self.repeat_exact_match_count + self.repeat_mismatch_count != 8:
            raise ValueError("initial repeat counts must cover all repeat pairs")
        if self.adjudication_required != bool(self.repeat_mismatch_count):
            raise ValueError("initial repeat adjudication flag is inconsistent")
        if sum(item.exact_match for item in self.pair_results) != self.repeat_exact_match_count:
            raise ValueError("initial repeat pair results contradict their count")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("initial label receipt does not match its payload")
        return self


class RepeatAdjudicationEntry(StrictModel):
    window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_presentation_ids: tuple[str, str]
    initial_judgments: tuple[PersonaAnnotationJudgment, PersonaAnnotationJudgment]
    final_judgment: PersonaAnnotationJudgment
    adjudication_reason: str = Field(min_length=1)


class CompletedRepeatAdjudicationSet(StrictModel):
    schema_version: Literal[
        "persona-repeat-adjudication/0.1", "persona-repeat-adjudication/0.2"
    ] = "persona-repeat-adjudication/0.2"
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_by: Literal["represented_user"]
    instructions: tuple[str, ...] = Field(min_length=4, max_length=4)
    adjudications: tuple[RepeatAdjudicationEntry, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def adjudications_are_unique(self) -> CompletedRepeatAdjudicationSet:
        identifiers = tuple(item.window_id for item in self.adjudications)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("repeat adjudications must target unique windows")
        return self
