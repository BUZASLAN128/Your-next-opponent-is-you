from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import datetime
from typing import Literal, cast

from ynoy.direct_memory.codec import correction_payload_sha256, strict_loads
from ynoy.direct_memory.correction_validation import validate_operation
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import StoredCorrection, StoredReview, UserAuthorizationReceipt
from ynoy.direct_memory.reviews import ReviewOperations
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError
from ynoy.models.correction import InteractionCorrectionReceipt
from ynoy.models.review_state import ReviewedInteractionState
from ynoy.review_replay import replay_interaction_review


class CorrectionReader:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.sources = SourceOperations(database, clock)
        self.reviews = ReviewOperations(database, clock)

    def list_corrections(
        self, review_id: str, *, revision_cutoff: int | None = None
    ) -> tuple[StoredCorrection, ...]:
        if revision_cutoff is not None and revision_cutoff < 0:
            raise DataValidationError(
                "direct_memory_revision_invalid", "Revision cutoff cannot be negative."
            )
        stored = self.reviews.get_review(review_id)
        facts = self.reviews.review_facts(review_id)
        rows = self._rows(review_id, revision_cutoff=revision_cutoff)
        receipts: list[InteractionCorrectionReceipt] = []
        records = []
        for row in rows:
            record, receipt = self._read_row(row, stored, facts, receipts)
            receipts.append(receipt)
            records.append(record)
        return tuple(records)

    def _rows(
        self, review_id: str, *, revision_cutoff: int | None = None
    ) -> Sequence[sqlite3.Row]:
        with closing(self.database.connect()) as connection:
            query = "SELECT * FROM corrections WHERE review_id=?"
            parameters: tuple[object, ...] = (review_id,)
            if revision_cutoff is not None:
                query += " AND revision<=?"
                parameters = (review_id, revision_cutoff)
            return connection.execute(query + " ORDER BY revision", parameters).fetchall()

    def _read_row(
        self,
        row: sqlite3.Row,
        stored: StoredReview,
        facts: Sequence[Mapping[str, object]],
        receipts: Sequence[InteractionCorrectionReceipt],
    ) -> tuple[StoredCorrection, InteractionCorrectionReceipt]:
        try:
            return self._validated_row(row, stored, facts, receipts)
        except Exception as exc:
            if isinstance(exc, DataValidationError):
                raise
            raise DataValidationError(
                "direct_memory_correction_integrity",
                "Stored correction wrapper failed verification.",
            ) from exc

    def _validated_row(
        self,
        row: sqlite3.Row,
        stored: StoredReview,
        facts: Sequence[Mapping[str, object]],
        receipts: Sequence[InteractionCorrectionReceipt],
    ) -> tuple[StoredCorrection, InteractionCorrectionReceipt]:
        operation = str(row["operation"])
        correction = InteractionCorrectionReceipt.model_validate(
            strict_loads(row["correction_json"])
        )
        authorization = UserAuthorizationReceipt.model_validate(
            strict_loads(row["authorization_json"])
        )
        supersessions = _supersessions(row["supersessions_json"])
        validate_operation(
            self.database, operation, correction.decisions, stored.project, facts, supersessions
        )
        self.sources.verify_authorization(
            authorization,
            action=operation,
            payload_sha256=correction_payload_sha256(
                correction.decisions, operation=operation, supersessions=supersessions
            ),
            subject_id=stored.review.subject_id,
            review_sha256=stored.review_sha256,
            allow_consumed=True,
        )
        chain = (*receipts, correction)
        state = replay_interaction_review(stored.review, chain)
        saved_state = ReviewedInteractionState.model_validate(strict_loads(row["state_json"]))
        recorded_at = datetime.fromisoformat(row["recorded_at"])
        _check_row_binding(row, stored, correction, state, saved_state)
        record = StoredCorrection(
            review_id=stored.review_id,
            project=stored.project,
            operation=cast(Literal["correct", "retract", "supersede"], operation),
            correction=correction,
            state=saved_state,
            authorization=authorization,
            supersessions=supersessions,
            recorded_at=recorded_at,
            revision=int(row["revision"]),
        )
        return record, correction


def _supersessions(value: str) -> dict[str, str]:
    decoded = strict_loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("invalid supersession mapping")
    return {str(key): str(item) for key, item in decoded.items()}


def _check_row_binding(
    row: sqlite3.Row,
    stored: StoredReview,
    correction: InteractionCorrectionReceipt,
    state: ReviewedInteractionState,
    saved_state: ReviewedInteractionState,
) -> None:
    if (
        state.state_sha256 != saved_state.state_sha256
        or correction.review_sha256 != stored.review_sha256
        or str(correction.record_id) != row["correction_id"]
        or row["project"] != stored.project
    ):
        raise ValueError("correction wrapper binding mismatch")


__all__ = ["CorrectionReader"]
