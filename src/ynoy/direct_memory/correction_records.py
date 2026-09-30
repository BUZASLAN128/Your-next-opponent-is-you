from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import datetime

from ynoy.direct_memory.codec import strict_dumps
from ynoy.direct_memory.models import StoredReview
from ynoy.models.correction import InteractionCorrectionReceipt
from ynoy.models.review_state import ReviewedInteractionState


def insert_correction_record(
    connection: sqlite3.Connection,
    stored: StoredReview,
    correction: InteractionCorrectionReceipt,
    state: ReviewedInteractionState,
    auth_json: str,
    operation: str,
    supersessions: Mapping[str, str],
    recorded_at: datetime,
    revision: int,
) -> None:
    connection.execute(
        "INSERT INTO corrections VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            str(correction.record_id),
            stored.review_id,
            stored.project,
            operation,
            strict_dumps(correction.model_dump(mode="json")),
            strict_dumps(state.model_dump(mode="json")),
            auth_json,
            strict_dumps(dict(sorted(supersessions.items()))),
            recorded_at.isoformat(),
            revision,
        ),
    )


__all__ = ["insert_correction_record"]
