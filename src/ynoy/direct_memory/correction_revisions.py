from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import cast

from ynoy.direct_memory.ledger import append_revision_record
from ynoy.direct_memory.models import (
    ProvenanceState,
    RevisionKind,
    StoredReview,
    UserAuthorizationReceipt,
)
from ynoy.direct_memory.reviews import ReviewOperations
from ynoy.models import ClaimReviewDecision, RejectClaimDecision
from ynoy.models.correction import (
    ConfirmClaimDecision,
    InteractionCorrectionReceipt,
    ProposeForCoreDecision,
)


def append_outcome_revisions(
    reviews: ReviewOperations,
    connection: sqlite3.Connection,
    stored: StoredReview,
    correction: InteractionCorrectionReceipt,
    decisions: Sequence[ClaimReviewDecision],
    claim_to_fact: Mapping[str, str],
    operation: str,
    supersessions: Mapping[str, str],
    authorization: UserAuthorizationReceipt,
    recorded_at: datetime,
    revision: int,
    interpretation_time: datetime | None,
) -> None:
    links = reviews.review_facts(stored.review_id)
    evidence_by_claim = {
        str(item["claim_id"]): tuple(str(value) for value in cast(list[str], item["evidence_ids"]))
        for item in links
    }
    for decision in decisions:
        _append_one_outcome(
            connection,
            stored,
            correction,
            decision,
            claim_to_fact[str(decision.claim_id)],
            evidence_by_claim[str(decision.claim_id)],
            operation,
            supersessions,
            authorization,
            recorded_at,
            revision,
            interpretation_time,
        )


def _append_one_outcome(
    connection: sqlite3.Connection,
    stored: StoredReview,
    correction: InteractionCorrectionReceipt,
    decision: ClaimReviewDecision,
    fact_key: str,
    evidence_ids: tuple[str, ...],
    operation: str,
    supersessions: Mapping[str, str],
    authorization: UserAuthorizationReceipt,
    recorded_at: datetime,
    revision: int,
    interpretation_time: datetime | None,
) -> None:
    if isinstance(decision, RejectClaimDecision):
        state = ProvenanceState.REJECTED
        kind = _rejection_kind(operation)
        related = supersessions.get(fact_key) if operation == "supersede" else None
    elif isinstance(decision, ConfirmClaimDecision):
        state, kind, related = ProvenanceState.ACCEPTED, RevisionKind.ASSERTION, None
    elif isinstance(decision, ProposeForCoreDecision):
        state, kind, related = ProvenanceState.PROPOSED, RevisionKind.ASSERTION, None
    else:
        state, kind, related = ProvenanceState.CORRECTED, RevisionKind.CORRECTION, None
    append_revision_record(
        connection,
        project=stored.project,
        fact_key=fact_key,
        evidence_ids=evidence_ids,
        state=state,
        kind=kind,
        payload={
            "review_sha256": stored.review_sha256,
            "correction_sha256": correction.receipt_sha256,
            "decision": decision.model_dump(mode="json"),
            "operation": operation,
        },
        event_time=interpretation_time,
        recorded_at=recorded_at,
        authorization=authorization,
        tool_receipt_id=None,
        related_fact_key=related,
        revision=revision,
    )


def _rejection_kind(operation: str) -> RevisionKind:
    if operation == "retract":
        return RevisionKind.RETRACTION
    if operation == "supersede":
        return RevisionKind.SUPERSESSION
    return RevisionKind.CORRECTION


__all__ = ["append_outcome_revisions"]
