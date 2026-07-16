from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_labels import PersonaAnnotationJudgment
from ynoy.util import canonical_sha256

ProposalReviewActionName = Literal["confirm", "correct", "not_mine"]


class PersonaProposalReviewAction(StrictModel):
    presentation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    order: int = Field(ge=1, le=32)
    proposed_judgment: PersonaAnnotationJudgment | None = None
    allowed_actions: tuple[ProposalReviewActionName, ...]
    action: ProposalReviewActionName | None = None
    corrected_judgment: PersonaAnnotationJudgment | None = None

    @model_validator(mode="after")
    def action_matches_proposal(self) -> PersonaProposalReviewAction:
        expected: tuple[ProposalReviewActionName, ...] = (
            ("confirm", "correct", "not_mine")
            if self.proposed_judgment is not None
            else ("correct", "not_mine")
        )
        if self.allowed_actions != expected:
            raise ValueError("proposal review actions do not match proposal availability")
        if self.action == "confirm" and self.proposed_judgment is None:
            raise ValueError("a missing model proposal cannot be confirmed")
        if self.action != "correct" and self.corrected_judgment is not None:
            raise ValueError("only a correction may carry a corrected judgment")
        return self

    @property
    def resolved(self) -> bool:
        return self.action is not None and (
            self.action != "correct" or self.corrected_judgment is not None
        )


class PersonaProposalReviewDraft(StrictModel):
    schema_version: Literal["persona-proposal-review/0.1"] = "persona-proposal-review/0.1"
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_by: Literal["represented_user"] | None = None
    instructions: tuple[str, ...] = Field(min_length=3, max_length=3)
    actions: tuple[PersonaProposalReviewAction, ...] = Field(min_length=8, max_length=12)

    @model_validator(mode="after")
    def review_shape_is_consistent(self) -> PersonaProposalReviewDraft:
        identifiers = tuple(item.presentation_id for item in self.actions)
        orders = tuple(item.order for item in self.actions)
        if len(set(identifiers)) != len(identifiers) or len(set(orders)) != len(orders):
            raise ValueError("proposal review actions must target unique cards")
        if self.completed_by is not None and not all(item.resolved for item in self.actions):
            raise ValueError("completed proposal review still has unresolved actions")
        return self


class SealedPersonaProposalReviewDecision(StrictModel):
    presentation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    order: int = Field(ge=1, le=32)
    action: ProposalReviewActionName
    proposed_judgment: PersonaAnnotationJudgment | None = None
    final_judgment: PersonaAnnotationJudgment
    interpretation_authority: Literal["represented_user_local_attestation"] = (
        "represented_user_local_attestation"
    )
    identity_authentication: Literal["local_operator_attestation_not_cryptographic"] = (
        "local_operator_attestation_not_cryptographic"
    )
    core_eligible: Literal[False] = False
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def decision_matches_action(self) -> SealedPersonaProposalReviewDecision:
        if self.action == "confirm" and (
            self.proposed_judgment is None or self.final_judgment != self.proposed_judgment
        ):
            raise ValueError("confirmed review must preserve the exact model proposal")
        if self.action == "not_mine" and (
            not self.final_judgment.exclude_from_persona or not self.final_judgment.should_abstain
        ):
            raise ValueError("not-mine review must remain abstaining and outside persona")
        return self


class CompletedPersonaProposalReview(StrictModel):
    schema_version: Literal["persona-proposal-review-sealed/0.1"] = (
        "persona-proposal-review-sealed/0.1"
    )
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_by: Literal["represented_user"] = "represented_user"
    decisions: tuple[SealedPersonaProposalReviewDecision, ...] = Field(min_length=8, max_length=12)

    @model_validator(mode="after")
    def decisions_are_unique(self) -> CompletedPersonaProposalReview:
        identifiers = tuple(item.presentation_id for item in self.decisions)
        orders = tuple(item.order for item in self.decisions)
        if len(set(identifiers)) != len(identifiers) or len(set(orders)) != len(orders):
            raise ValueError("sealed proposal review decisions must target unique cards")
        return self


class PersonaProposalReviewReceipt(StrictModel):
    schema_version: Literal["persona-proposal-review-receipt/0.1"] = (
        "persona-proposal-review-receipt/0.1"
    )
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_count: int = Field(ge=8, le=12)
    confirm_count: int = Field(ge=0, le=12)
    correct_count: int = Field(ge=0, le=12)
    not_mine_count: int = Field(ge=0, le=12)
    confirmed_proposal_count: int = Field(ge=0, le=12)
    proposal_available_count: int = Field(ge=0, le=12)
    interpretation_authority: Literal["represented_user_local_attestation"] = (
        "represented_user_local_attestation"
    )
    identity_authentication: Literal["local_operator_attestation_not_cryptographic"] = (
        "local_operator_attestation_not_cryptographic"
    )
    model_provider_used: Literal[True] = True
    represented_user_review_used: Literal[True] = True
    persona_quality_claimed: Literal[False] = False
    protected_holdout_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_matches(self) -> PersonaProposalReviewReceipt:
        if self.confirm_count + self.correct_count + self.not_mine_count != self.reviewed_count:
            raise ValueError("proposal review action counts must cover the review set")
        if (
            self.confirmed_proposal_count != self.confirm_count
            or self.confirmed_proposal_count > self.proposal_available_count
        ):
            raise ValueError("confirmed proposal count is inconsistent")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("proposal review receipt does not match its payload")
        return self
