from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ynoy.direct_memory.data_plane import DataPlane
from ynoy.models import AtomicClaimProposal, InteractionReview, Speaker, StrictModel
from ynoy.models.correction import InteractionCorrectionReceipt
from ynoy.models.decision_brief import DecisionBrief
from ynoy.models.review_state import ReviewedInteractionState
from ynoy.util import canonical_sha256

Sha256 = Field(pattern=r"^[0-9a-f]{64}$")


class SourceType(StrEnum):
    IMPORTED = "imported"
    LIVE_USER_INPUT = "live_user_input"
    TOOL_RESULT = "tool_result"


class ProvenanceState(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    INTENT = "intent"
    REPORTED_DONE = "reported_done"
    TOOL_VERIFIED = "tool_verified"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    UNCERTAIN = "uncertain"


class RevisionKind(StrEnum):
    ASSERTION = "assertion"
    CORRECTION = "correction"
    RETRACTION = "retraction"
    SUPERSESSION = "supersession"


class SourceEvent(StrictModel):
    data_plane: DataPlane
    source_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    speaker: Speaker
    said_at: datetime | None
    recorded_at: datetime
    exact_text: str = Field(min_length=1)
    sha256: str = Sha256
    source_type: SourceType
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def event_is_canonical(self) -> SourceEvent:
        if any(value != value.strip() for value in (self.source_id, self.project)):
            raise ValueError("source identifiers must be trimmed")
        if self.recorded_at.utcoffset() is None or (
            self.said_at is not None and self.said_at.utcoffset() is None
        ):
            raise ValueError("source event timestamps must be timezone-aware")
        from ynoy.util import sha256_text

        if self.sha256 != sha256_text(self.exact_text):
            raise ValueError("source event hash does not match exact text")
        if self.source_type == SourceType.LIVE_USER_INPUT and self.speaker != Speaker.USER:
            raise ValueError("live user input must have a user speaker")
        if self.source_type == SourceType.TOOL_RESULT and self.speaker != Speaker.TOOL:
            raise ValueError("tool result must have a tool speaker")
        return self


class FactProposal(StrictModel):
    fact_key: str = Field(min_length=1, max_length=240)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    proposal: AtomicClaimProposal

    @model_validator(mode="after")
    def fact_link_is_canonical(self) -> FactProposal:
        if self.fact_key != self.fact_key.strip():
            raise ValueError("fact key must be trimmed")
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or any(
            not value or value != value.strip() for value in self.evidence_ids
        ):
            raise ValueError("fact evidence identifiers must be unique and trimmed")
        return self


class AuthorizationIntent(StrictModel):
    action: Literal["correct", "retract", "supersede", "source_authorship", "claim_revision"]
    payload_sha256: str = Sha256
    subject_id: str = Field(min_length=1)
    review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def intent_is_bound(self) -> AuthorizationIntent:
        if self.subject_id != self.subject_id.strip():
            raise ValueError("authorization subject must be trimmed")
        if self.action == "source_authorship" and self.review_sha256 is not None:
            raise ValueError("source authorship cannot bind an interaction review")
        if self.action in {"correct", "retract", "supersede"} and self.review_sha256 is None:
            raise ValueError("review correction authorization requires a review hash")
        return self


class UserAuthorizationReceipt(StrictModel):
    action: str
    payload_sha256: str = Sha256
    subject_id: str = Field(min_length=1)
    review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    live_user_source_id: str = Field(min_length=1)
    live_user_source_sha256: str = Sha256
    authorized_at: datetime
    authorization_sha256: str = Sha256

    @model_validator(mode="after")
    def receipt_is_sealed(self) -> UserAuthorizationReceipt:
        from ynoy.util import canonical_sha256

        if self.authorized_at.utcoffset() is None:
            raise ValueError("authorization time must be timezone-aware")
        if self.authorization_sha256 != canonical_sha256(
            self.model_dump(mode="json", exclude={"authorization_sha256"})
        ):
            raise ValueError("authorization hash does not match its payload")
        return self


class ToolReceipt(StrictModel):
    tool_receipt_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    input_sha256: str = Sha256
    result: dict[str, object]
    result_sha256: str = Sha256
    recorded_at: datetime
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def receipt_is_consistent(self) -> ToolReceipt:
        from ynoy.util import canonical_sha256

        if self.recorded_at.utcoffset() is None:
            raise ValueError("tool receipt time must be timezone-aware")
        if canonical_sha256(self.result) != self.result_sha256:
            raise ValueError("tool result hash does not match its payload")
        if any(value != value.strip() for value in (self.project, self.tool_name, self.operation)):
            raise ValueError("tool receipt identifiers must be trimmed")
        return self


class StoredReview(StrictModel):
    review_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    review_sha256: str = Sha256
    review: InteractionReview
    revision: int = Field(ge=1)


class StoredCorrection(StrictModel):
    review_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    operation: Literal["correct", "retract", "supersede"]
    correction: InteractionCorrectionReceipt
    state: ReviewedInteractionState
    authorization: UserAuthorizationReceipt
    supersessions: dict[str, str]
    recorded_at: datetime
    revision: int = Field(ge=1)


class ClaimRevision(StrictModel):
    revision_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    fact_key: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    state: ProvenanceState
    kind: RevisionKind
    payload: dict[str, object]
    event_time: datetime | None
    recorded_at: datetime
    authorization: UserAuthorizationReceipt | None
    tool_receipt_id: str | None = None
    related_fact_key: str | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def provenance_is_separate_from_truth(self) -> ClaimRevision:
        if self.recorded_at.utcoffset() is None or (
            self.event_time is not None and self.event_time.utcoffset() is None
        ):
            raise ValueError("claim revision times must be timezone-aware")
        if self.state == ProvenanceState.TOOL_VERIFIED and self.tool_receipt_id is None:
            raise ValueError("tool-verified state requires a persisted tool receipt")
        if self.kind == RevisionKind.SUPERSESSION and not self.related_fact_key:
            raise ValueError("supersession requires the related replacement fact key")
        if self.kind != RevisionKind.SUPERSESSION and self.related_fact_key is not None:
            raise ValueError("only supersession may name a related replacement fact key")
        if self.state != ProvenanceState.PROPOSED and self.authorization is None:
            raise ValueError("non-proposed claim states require explicit user authorization")
        return self


class DirectMemoryBrief(StrictModel):
    data_plane: DataPlane
    project: str = Field(min_length=1)
    as_of: datetime
    known_at: datetime
    source_events: tuple[SourceEvent, ...]
    claim_revisions: tuple[ClaimRevision, ...]
    native_briefs: tuple[DecisionBrief, ...]
    native_brief_hashes: tuple[str, ...]
    unresolved_conflicts: tuple[tuple[str, ...], ...]
    abstained: bool
    abstention_reasons: tuple[str, ...]
    authority: Literal["none"] = "none"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def cutoff_is_valid(self) -> DirectMemoryBrief:
        if self.as_of.utcoffset() is None or self.known_at.utcoffset() is None:
            raise ValueError("brief cutoffs must be timezone-aware")
        if len(self.native_briefs) != len(self.native_brief_hashes):
            raise ValueError("native brief hashes must align with native briefs")
        expected_hashes = tuple(
            canonical_sha256(item.model_dump(mode="json")) for item in self.native_briefs
        )
        if self.native_brief_hashes != expected_hashes:
            raise ValueError("native brief hashes do not match their payloads")
        if len(set(self.abstention_reasons)) != len(self.abstention_reasons):
            raise ValueError("brief abstention reasons must be unique")
        if self.abstained != bool(self.abstention_reasons):
            raise ValueError("brief abstention must match its reasons")
        if bool(self.unresolved_conflicts) != ("unresolved_conflict" in self.abstention_reasons):
            raise ValueError("brief conflicts must force an explicit abstention")
        return self


__all__ = [
    "AuthorizationIntent",
    "ClaimRevision",
    "DirectMemoryBrief",
    "FactProposal",
    "ProvenanceState",
    "RevisionKind",
    "SourceEvent",
    "SourceType",
    "StoredCorrection",
    "StoredReview",
    "ToolReceipt",
    "UserAuthorizationReceipt",
]
