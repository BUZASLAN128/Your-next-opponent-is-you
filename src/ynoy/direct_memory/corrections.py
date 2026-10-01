from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import Literal, cast

from ynoy.correction import build_correction_receipt
from ynoy.direct_memory.codec import correction_payload_sha256, strict_dumps, strict_loads
from ynoy.direct_memory.correction_reader import CorrectionReader
from ynoy.direct_memory.correction_records import insert_correction_record
from ynoy.direct_memory.correction_revisions import append_outcome_revisions
from ynoy.direct_memory.correction_validation import (
    validate_correction_continuity,
    validate_kind,
    validate_operation,
)
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import StoredCorrection, StoredReview, UserAuthorizationReceipt
from ynoy.direct_memory.reviews import ReviewOperations
from ynoy.direct_memory.source_events import trusted_time
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError
from ynoy.models import ClaimReviewDecision
from ynoy.models.correction import InteractionCorrectionReceipt
from ynoy.models.review_state import ReviewedInteractionState
from ynoy.review_replay import replay_interaction_review, review_deletion_dependencies


class CorrectionOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock
        self.sources = SourceOperations(database, clock)
        self.reviews = ReviewOperations(database, clock)
        self.reader = CorrectionReader(database, clock)

    def apply_correction(
        self,
        review_id: str,
        decisions: Sequence[ClaimReviewDecision],
        authorization: UserAuthorizationReceipt,
        *,
        expected_revision: int,
        operation: str = "correct",
        supersessions: Mapping[str, str] | None = None,
    ) -> StoredCorrection:
        validate_kind(operation)
        selected_supersessions: Mapping[str, str] = MappingProxyType(
            {} if supersessions is None else dict(supersessions.items())
        )
        stored = self.reviews.get_review(review_id)
        safe_decisions = tuple(decisions)
        facts = self.reviews.review_facts(review_id)
        claim_to_fact = validate_operation(
            self.database,
            operation,
            safe_decisions,
            stored.project,
            facts,
            selected_supersessions,
        )
        digest = correction_payload_sha256(
            safe_decisions, operation=operation, supersessions=selected_supersessions
        )
        self.sources.verify_authorization(
            authorization,
            action=operation,
            payload_sha256=digest,
            subject_id=stored.review.subject_id,
            review_sha256=stored.review_sha256,
        )
        existing = self.reader.list_corrections(review_id)
        correction, state = self._build_correction(stored, existing, safe_decisions)
        self._require_same_project(stored.project, authorization)
        return self._persist_correction(
            stored,
            correction,
            state,
            safe_decisions,
            claim_to_fact,
            authorization,
            expected_revision,
            operation,
            selected_supersessions,
        )

    def list_corrections(
        self, review_id: str, *, revision_cutoff: int | None = None
    ) -> tuple[StoredCorrection, ...]:
        return self.reader.list_corrections(review_id, revision_cutoff=revision_cutoff)

    def _build_correction(
        self,
        stored: StoredReview,
        existing: Sequence[StoredCorrection],
        decisions: tuple[ClaimReviewDecision, ...],
    ) -> tuple[InteractionCorrectionReceipt, ReviewedInteractionState]:
        old_receipts = tuple(item.correction for item in existing)
        previous_state = replay_interaction_review(stored.review, old_receipts)
        validate_correction_continuity(previous_state, decisions)
        correction = build_correction_receipt(
            stored.review,
            decisions,
            previous_receipt=old_receipts[-1] if old_receipts else None,
            created_at=trusted_time(self.clock),
        )
        chain = (*old_receipts, correction)
        state = replay_interaction_review(stored.review, chain)
        if replay_interaction_review(stored.review, chain).state_sha256 != state.state_sha256:
            raise DataValidationError(
                "direct_memory_replay_nondeterministic",
                "Repeated native review replay changed state.",
            )
        review_deletion_dependencies(stored.review, chain)
        return correction, state

    def _persist_correction(
        self,
        stored: StoredReview,
        correction: InteractionCorrectionReceipt,
        state: ReviewedInteractionState,
        decisions: tuple[ClaimReviewDecision, ...],
        claim_to_fact: Mapping[str, str],
        authorization: UserAuthorizationReceipt,
        expected_revision: int,
        operation: str,
        supersessions: Mapping[str, str],
    ) -> StoredCorrection:
        recorded_at, revision = _write_correction(
            self.database,
            self.sources,
            self.reviews,
            stored,
            correction,
            state,
            decisions,
            claim_to_fact,
            authorization,
            expected_revision,
            operation,
            supersessions,
            self.clock,
        )
        return StoredCorrection(
            review_id=stored.review_id,
            project=stored.project,
            operation=cast(Literal["correct", "retract", "supersede"], operation),
            correction=correction,
            state=state,
            authorization=authorization,
            supersessions=dict(supersessions),
            recorded_at=recorded_at,
            revision=revision,
        )

    def _require_same_project(self, project: str, authorization: UserAuthorizationReceipt) -> None:
        event = self.sources.get_source_event(authorization.live_user_source_id)
        if event.project != project:
            raise DataValidationError(
                "direct_memory_authorization_mismatch",
                "Correction authorization belongs to another project.",
            )


def _write_correction(
    database: DirectMemoryDatabase,
    sources: SourceOperations,
    reviews: ReviewOperations,
    stored: StoredReview,
    correction: InteractionCorrectionReceipt,
    state: ReviewedInteractionState,
    decisions: tuple[ClaimReviewDecision, ...],
    claim_to_fact: Mapping[str, str],
    authorization: UserAuthorizationReceipt,
    expected_revision: int,
    operation: str,
    supersessions: Mapping[str, str],
    clock: Callable[[], datetime],
) -> tuple[datetime, int]:
    auth_json = strict_dumps(authorization.model_dump(mode="json"))
    source_event = sources.get_source_event(stored.source_id)
    interpretation_time = stored.review.source.event_time or source_event.said_at
    with database.mutation(stored.project, expected_revision) as (connection, revision):
        recorded_at = trusted_time(clock)
        _consume_authorization(sources, connection, stored, authorization, recorded_at, revision)
        _assert_chain_head(connection, stored.review_id, correction)
        insert_correction_record(
            connection,
            stored,
            correction,
            state,
            auth_json,
            operation,
            supersessions,
            recorded_at,
            revision,
        )
        _append_outcomes(
            reviews,
            connection,
            stored,
            correction,
            decisions,
            claim_to_fact,
            operation,
            supersessions,
            authorization,
            recorded_at,
            revision,
            interpretation_time,
        )
    return recorded_at, revision


def _consume_authorization(
    sources: SourceOperations,
    connection: sqlite3.Connection,
    stored: StoredReview,
    authorization: UserAuthorizationReceipt,
    recorded_at: datetime,
    revision: int,
) -> None:
    sources.consume_authorization(
        connection,
        authorization,
        project=stored.project,
        revision=revision,
        recorded_at=recorded_at,
    )


def _assert_chain_head(
    connection: sqlite3.Connection,
    review_id: str,
    correction: InteractionCorrectionReceipt,
) -> None:
    row = connection.execute(
        "SELECT correction_json FROM corrections WHERE review_id=? ORDER BY revision DESC LIMIT 1",
        (review_id,),
    ).fetchone()
    actual = None
    if row is not None:
        previous = InteractionCorrectionReceipt.model_validate(strict_loads(row["correction_json"]))
        actual = previous.receipt_sha256
    if correction.previous_receipt_sha256 != actual:
        raise DataValidationError(
            "direct_memory_stale_correction_head",
            "The correction chain changed before this revision could be appended.",
        )


def _append_outcomes(
    reviews: ReviewOperations,
    connection: sqlite3.Connection,
    stored: StoredReview,
    correction: InteractionCorrectionReceipt,
    decisions: tuple[ClaimReviewDecision, ...],
    claim_to_fact: Mapping[str, str],
    operation: str,
    supersessions: Mapping[str, str],
    authorization: UserAuthorizationReceipt,
    recorded_at: datetime,
    revision: int,
    interpretation_time: datetime | None,
) -> None:
    append_outcome_revisions(
        reviews,
        connection,
        stored,
        correction,
        decisions,
        claim_to_fact,
        operation,
        supersessions,
        authorization,
        recorded_at,
        revision,
        interpretation_time,
    )


__all__ = ["CorrectionOperations"]
