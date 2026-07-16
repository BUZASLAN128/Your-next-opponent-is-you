from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.interaction import AtomicClaimProposal
from ynoy.models.review_vocab import ReviewAction, ReviewOutcome
from ynoy.util import canonical_sha256

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ClaimReviewEvent(StrictModel):
    correction_receipt_id: UUID
    correction_receipt_sha256: Sha256Digest
    sequence: int = Field(ge=1)
    action: ReviewAction
    outcome: ReviewOutcome
    effective_claim_ids: tuple[UUID, ...]
    superseded_by_receipt_sha256: Sha256Digest | None = None


class ReviewedClaimState(StrictModel):
    original: AtomicClaimProposal
    effective_claims: tuple[AtomicClaimProposal, ...]
    outcome: ReviewOutcome
    active: bool
    core_review_requested: bool = False
    core_eligible: Literal[False] = False
    history: tuple[ClaimReviewEvent, ...]

    @model_validator(mode="after")
    def lifecycle_is_consistent(self) -> ReviewedClaimState:
        inactive = self.outcome in {ReviewOutcome.PENDING, ReviewOutcome.REJECTED}
        if self.active == inactive:
            raise ValueError("reviewed claim active flag contradicts its outcome")
        if inactive and self.effective_claims:
            raise ValueError("pending or rejected claim cannot have an effective interpretation")
        if not inactive and not self.effective_claims:
            raise ValueError("active reviewed claim requires an effective interpretation")
        if self.core_review_requested != (self.outcome == ReviewOutcome.CORE_REVIEW_REQUESTED):
            raise ValueError("core review request flag must match the lifecycle outcome")
        if any(
            item.receipt_id != self.original.receipt_id
            or item.subject_id != self.original.subject_id
            for item in self.effective_claims
        ):
            raise ValueError("effective claims must retain source receipt and subject")
        if self.outcome == ReviewOutcome.PENDING and self.history:
            raise ValueError("pending claim cannot have correction history")
        if self.outcome != ReviewOutcome.PENDING and not self.history:
            raise ValueError("resolved claim requires correction history")
        if self.history and self.history[-1].outcome != self.outcome:
            raise ValueError("latest correction history must match current outcome")
        sequences = tuple(item.sequence for item in self.history)
        if sequences != tuple(sorted(set(sequences))):
            raise ValueError("claim correction history must be ordered and unique")
        receipt_ids = tuple(item.correction_receipt_id for item in self.history)
        receipt_hashes = tuple(item.correction_receipt_sha256 for item in self.history)
        if len(set(receipt_ids)) != len(receipt_ids) or len(set(receipt_hashes)) != len(
            receipt_hashes
        ):
            raise ValueError("claim correction history receipts must be unique")
        for current, following in zip(self.history, self.history[1:], strict=False):
            if current.superseded_by_receipt_sha256 != following.correction_receipt_sha256:
                raise ValueError("historical correction must point to its superseding receipt")
        if self.history and self.history[-1].superseded_by_receipt_sha256 is not None:
            raise ValueError("latest correction cannot already be superseded")
        effective_ids = tuple(item.record_id for item in self.effective_claims)
        if self.history and self.history[-1].effective_claim_ids != effective_ids:
            raise ValueError("latest correction must identify the current effective claims")
        if any(
            item.outcome == ReviewOutcome.PENDING
            or (item.outcome == ReviewOutcome.REJECTED) != (not item.effective_claim_ids)
            for item in self.history
        ):
            raise ValueError("correction history outcome contradicts its effective claims")
        return self


class ReviewedInteractionState(StrictModel):
    """Deterministic replay projection; receipts remain the immutable history."""

    source_receipt_id: UUID
    source_name: str = Field(min_length=1)
    source_conversation_id: str = Field(min_length=1)
    source_turn_id: str = Field(min_length=1)
    review_sha256: Sha256Digest
    subject_id: str = Field(min_length=1)
    data_class: DataClass
    correction_receipt_ids: tuple[UUID, ...]
    correction_receipt_hashes: tuple[Sha256Digest, ...]
    receipt_head_sha256: Sha256Digest | None = None
    claims: tuple[ReviewedClaimState, ...] = Field(min_length=1)
    review_status: Literal["awaiting_user_confirmation", "partially_reviewed", "reviewed"]
    pending_claim_ids: tuple[UUID, ...]
    state_sha256: Sha256Digest
    database_used: Literal[False] = False
    provider_used: Literal[False] = False
    persistence_status: Literal["not_persisted"] = "not_persisted"
    authority: Literal["none"] = "none"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def replay_state_is_consistent(self) -> ReviewedInteractionState:
        source_identifiers = (
            self.source_name,
            self.source_conversation_id,
            self.source_turn_id,
        )
        if any(value != value.strip() for value in source_identifiers):
            raise ValueError("reviewed interaction source identifiers must be trimmed")
        if self.subject_id != self.subject_id.strip():
            raise ValueError("reviewed interaction subject must be trimmed")
        if len(self.correction_receipt_ids) != len(self.correction_receipt_hashes):
            raise ValueError("correction receipt identifiers and hashes must align")
        if len(set(self.correction_receipt_ids)) != len(self.correction_receipt_ids):
            raise ValueError("correction receipt identifiers must be unique")
        if len(set(self.correction_receipt_hashes)) != len(self.correction_receipt_hashes):
            raise ValueError("correction receipt hashes must be unique")
        expected_head = (
            self.correction_receipt_hashes[-1] if self.correction_receipt_hashes else None
        )
        if self.receipt_head_sha256 != expected_head:
            raise ValueError("receipt head must match the latest correction hash")
        expected_pending = tuple(
            item.original.record_id for item in self.claims if item.outcome == ReviewOutcome.PENDING
        )
        if self.pending_claim_ids != expected_pending:
            raise ValueError("pending claim identifiers must match replayed claim state")
        expected_status = _review_status(bool(self.correction_receipt_ids), bool(expected_pending))
        if self.review_status != expected_status:
            raise ValueError("review status does not match correction coverage")
        if len({item.original.record_id for item in self.claims}) != len(self.claims):
            raise ValueError("reviewed interaction claims must be unique")
        if any(
            item.original.receipt_id != self.source_receipt_id
            or item.original.subject_id != self.subject_id
            for item in self.claims
        ):
            raise ValueError("reviewed claims must retain source receipt and subject")
        _validate_replay_receipt_references(self)
        payload = self.model_dump(mode="json", exclude={"state_sha256"})
        if self.state_sha256 != canonical_sha256(payload):
            raise ValueError("replayed state hash does not match its canonical payload")
        return self


def _validate_replay_receipt_references(state: ReviewedInteractionState) -> None:
    seen_receipt_ids: set[UUID] = set()
    seen_receipt_hashes: set[str] = set()
    for claim in state.claims:
        for event in claim.history:
            index = event.sequence - 1
            if index >= len(state.correction_receipt_ids) or (
                event.correction_receipt_id != state.correction_receipt_ids[index]
                or event.correction_receipt_sha256 != state.correction_receipt_hashes[index]
            ):
                raise ValueError("claim history must reference the replay receipt chain")
            seen_receipt_ids.add(event.correction_receipt_id)
            seen_receipt_hashes.add(event.correction_receipt_sha256)
    if seen_receipt_ids != set(state.correction_receipt_ids) or seen_receipt_hashes != set(
        state.correction_receipt_hashes
    ):
        raise ValueError("every replay receipt must resolve at least one claim")


def _review_status(has_receipts: bool, has_pending: bool) -> str:
    if not has_receipts:
        return "awaiting_user_confirmation"
    return "partially_reviewed" if has_pending else "reviewed"


class DeletionDependencyProjection(StrictModel):
    source_receipt_id: UUID
    review_sha256: Sha256Digest
    dependent_claim_ids: tuple[UUID, ...]
    dependent_correction_receipt_ids: tuple[UUID, ...]
    dependent_correction_hashes: tuple[Sha256Digest, ...]
    total_dependency_count: int = Field(ge=1)
    deletion_performed: Literal[False] = False
    database_used: Literal[False] = False

    @model_validator(mode="after")
    def dependency_count_is_consistent(self) -> DeletionDependencyProjection:
        expected = 1 + len(self.dependent_claim_ids) + len(self.dependent_correction_receipt_ids)
        if self.total_dependency_count != expected:
            raise ValueError("deletion dependency count must include source and all derivatives")
        if len(self.dependent_correction_receipt_ids) != len(self.dependent_correction_hashes):
            raise ValueError("deletion correction identifiers and hashes must align")
        if len(set(self.dependent_claim_ids)) != len(self.dependent_claim_ids):
            raise ValueError("deletion dependency claim identifiers must be unique")
        if len(set(self.dependent_correction_receipt_ids)) != len(
            self.dependent_correction_receipt_ids
        ):
            raise ValueError("deletion dependency correction identifiers must be unique")
        if len(set(self.dependent_correction_hashes)) != len(self.dependent_correction_hashes):
            raise ValueError("deletion dependency correction hashes must be unique")
        return self
