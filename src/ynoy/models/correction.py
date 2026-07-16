from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
from ynoy.models.base import (
    ClaimHolder,
    DataClass,
    RecordBase,
    ScopeRef,
    SourceAuthority,
    Speaker,
    StrictModel,
)
from ynoy.models.interaction import AtomicClaimProposal
from ynoy.models.review_vocab import ReviewAction, TargetLayer
from ynoy.util import canonical_sha256


def _is_bounded_reason(value: str) -> bool:
    return (
        bool(value.strip())
        and value == value.strip()
        and len(value.encode("utf-8")) <= DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
    )


class ClaimReviewDecisionBase(StrictModel):
    claim_id: UUID
    subject_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def subject_is_canonical(self) -> ClaimReviewDecisionBase:
        if self.subject_id != self.subject_id.strip():
            raise ValueError("review decision subject must be trimmed")
        return self


class ConfirmClaimDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.CONFIRM] = ReviewAction.CONFIRM


class RejectClaimDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.REJECT] = ReviewAction.REJECT
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def reason_is_bounded(self) -> RejectClaimDecision:
        if not _is_bounded_reason(self.reason):
            raise ValueError("rejection reason must be trimmed and bounded")
        return self


class SplitClaimDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.SPLIT] = ReviewAction.SPLIT
    replacements: tuple[AtomicClaimProposal, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def replacements_are_unique(self) -> SplitClaimDecision:
        ids = tuple(item.record_id for item in self.replacements)
        if len(ids) != len(set(ids)):
            raise ValueError("split replacement identifiers must be unique")
        return self


class NarrowScopeClaimDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.NARROW_SCOPE] = ReviewAction.NARROW_SCOPE
    replacement_scope: ScopeRef


class MarkTemporaryClaimDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.MARK_TEMPORARY] = ReviewAction.MARK_TEMPORARY
    valid_until: datetime

    @model_validator(mode="after")
    def time_is_aware(self) -> MarkTemporaryClaimDecision:
        if self.valid_until.utcoffset() is None:
            raise ValueError("temporary validity must use a timezone-aware timestamp")
        return self


class MakeProjectRuleDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.MAKE_PROJECT_RULE] = ReviewAction.MAKE_PROJECT_RULE
    target_layer: Literal[TargetLayer.PROJECT_CONSTITUTION, TargetLayer.SCOPED_POLICY]


class RejectInferenceDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.REJECT_INFERENCE] = ReviewAction.REJECT_INFERENCE


class ProposeForCoreDecision(ClaimReviewDecisionBase):
    action: Literal[ReviewAction.PROPOSE_FOR_CORE] = ReviewAction.PROPOSE_FOR_CORE


type ClaimReviewDecision = Annotated[
    ConfirmClaimDecision
    | RejectClaimDecision
    | SplitClaimDecision
    | NarrowScopeClaimDecision
    | MarkTemporaryClaimDecision
    | MakeProjectRuleDecision
    | RejectInferenceDecision
    | ProposeForCoreDecision,
    Field(discriminator="action"),
]


class InteractionCorrectionReceipt(RecordBase):
    """An explicit, non-persisting user correction bound to one atomic review."""

    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_receipt_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sequence: int = Field(ge=1)
    subject_id: str = Field(min_length=1)
    actor: Literal[Speaker.USER] = Speaker.USER
    claim_holder: Literal[ClaimHolder.REPRESENTED_USER] = ClaimHolder.REPRESENTED_USER
    source_authority: Literal[SourceAuthority.EXPLICIT_USER_STATEMENT] = (
        SourceAuthority.EXPLICIT_USER_STATEMENT
    )
    explicit_adoption: Literal[True] = True
    correction_data_class: DataClass
    synthetic: bool
    decisions: tuple[ClaimReviewDecision, ...] = Field(min_length=1)
    decision_count: int = Field(ge=1)
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_used: Literal[False] = False
    provider_used: Literal[False] = False
    persistence_status: Literal["not_persisted"] = "not_persisted"
    authority: Literal["none"] = "none"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def correction_contract_is_consistent(self) -> InteractionCorrectionReceipt:
        if self.subject_id != self.subject_id.strip():
            raise ValueError("correction receipt subject must be trimmed")
        if self.created_at.utcoffset() is None:
            raise ValueError("correction receipt time must be timezone-aware")
        if self.sequence == 1 and self.previous_receipt_sha256 is not None:
            raise ValueError("first correction receipt cannot have a predecessor")
        if self.sequence > 1 and self.previous_receipt_sha256 is None:
            raise ValueError("later correction receipt requires a predecessor")
        if self.decision_count != len(self.decisions):
            raise ValueError("correction decision count must match decisions")
        claim_ids = tuple(item.claim_id for item in self.decisions)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("one correction receipt cannot decide one claim twice")
        if any(item.subject_id != self.subject_id for item in self.decisions):
            raise ValueError("correction decisions must match receipt subject")
        expected_class = (
            DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.DERIVED_IDENTITY
        )
        if self.correction_data_class != expected_class:
            raise ValueError("correction data class must match synthetic state")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("correction receipt hash does not match its canonical payload")
        return self
