from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.interaction import ReviewProviderEvidence
from ynoy.models.persona_labels import PersonaAnnotationJudgment
from ynoy.util import canonical_sha256

ProposalPassName = Literal["direct", "skeptical"]
ProposalStatus = Literal["stable", "disagreement", "partial_invalid", "invalid"]
ProposalRunStatus = Literal["review_ready", "unreliable"]


class PersonaProposalPass(StrictModel):
    pass_name: ProposalPassName
    method: Literal["local_model", "deterministic_guard"] = "local_model"
    judgment: PersonaAnnotationJudgment


class PersonaModelProposal(StrictModel):
    presentation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    order: int = Field(ge=1, le=32)
    focus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    direct: PersonaProposalPass | None = None
    skeptical: PersonaProposalPass | None = None
    chosen_judgment: PersonaAnnotationJudgment | None = None
    status: ProposalStatus
    risk_reasons: tuple[str, ...]
    selected_for_review: bool
    interpretation_authority: Literal["none_model_proposal_only"] = "none_model_proposal_only"
    core_eligible: Literal[False] = False
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def pass_state_is_consistent(self) -> PersonaModelProposal:
        valid = tuple(item for item in (self.direct, self.skeptical) if item is not None)
        same = len(valid) == 2 and valid[0].judgment == valid[1].judgment
        expected = (
            "stable"
            if same
            else "disagreement"
            if len(valid) == 2
            else "partial_invalid"
            if len(valid) == 1
            else "invalid"
        )
        expected_choice = valid[0].judgment if same or len(valid) == 1 else None
        if self.status != expected or self.chosen_judgment != expected_choice:
            raise ValueError("persona proposal pass state is inconsistent")
        if self.status != "stable" and "model_pass_unstable" not in self.risk_reasons:
            raise ValueError("unstable proposal must retain its risk reason")
        return self


class PersonaProposalRunReceipt(StrictModel):
    schema_version: Literal["persona-model-proposals/0.1", "persona-model-proposals/0.2"] = (
        "persona-model-proposals/0.2"
    )
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ProposalRunStatus
    presentation_count: Literal[32] = 32
    stable_count: int = Field(ge=0, le=32)
    disagreement_count: int = Field(ge=0, le=32)
    blind_repeat_disagreement_count: int = Field(ge=0, le=8)
    deterministic_guard_pass_count: int = Field(default=0, ge=0, le=64)
    invalid_pass_count: int = Field(ge=0, le=64)
    base_audit_count: Literal[8] = 8
    required_review_count: int = Field(ge=8, le=32)
    review_burden_cap: Literal[12] = 12
    proposal_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_selection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_evidence: ReviewProviderEvidence
    model_provider_used: Literal[True] = True
    represented_user_labels_used: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    protected_holdout_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> PersonaProposalRunReceipt:
        legacy = self._is_legacy_01
        expected_status = (
            "review_ready" if self.required_review_count <= self.review_burden_cap else "unreliable"
        )
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if legacy:
            payload.pop("deterministic_guard_pass_count")
        expected = canonical_sha256(payload)
        if self.status != expected_status or self.receipt_sha256 != expected:
            raise ValueError("persona proposal receipt does not match its payload")
        return self

    @property
    def _is_legacy_01(self) -> bool:
        return (
            self.schema_version == "persona-model-proposals/0.1"
            and "deterministic_guard_pass_count" not in self.model_fields_set
        )


class PersonaProposalBundle(StrictModel):
    proposals: tuple[PersonaModelProposal, ...] = Field(min_length=32, max_length=32)
    receipt: PersonaProposalRunReceipt

    @model_validator(mode="after")
    def proposals_match_receipt(self) -> PersonaProposalBundle:
        ids = tuple(item.presentation_id for item in self.proposals)
        if len(set(ids)) != 32:
            raise ValueError("persona proposal presentations must be unique")
        dumped = [item.model_dump(mode="json") for item in self.proposals]
        if self.receipt._is_legacy_01:
            for proposal in dumped:
                for pass_name in ("direct", "skeptical"):
                    pass_payload = proposal[pass_name]
                    if pass_payload is not None:
                        pass_payload.pop("method")
        digest = canonical_sha256(dumped)
        if digest != self.receipt.proposal_set_sha256:
            raise ValueError("persona proposal bundle does not match its receipt")
        return self
