from __future__ import annotations

from contextlib import closing
from typing import TYPE_CHECKING

from ynoy.direct_memory.codec import strict_dumps
from ynoy.direct_memory.correction_reader import CorrectionReader
from ynoy.direct_memory.ledger import _claim_revision_from_row
from ynoy.direct_memory.models import StoredCorrection
from ynoy.direct_memory.payload_snapshot import _correction_revision_matches
from ynoy.errors import DataValidationError

if TYPE_CHECKING:
    from ynoy.direct_memory.claims import ClaimOperations


def verify_correction_revision_prefix(
    operations: ClaimOperations, project: str, revision_cutoff: int
) -> None:
    """Verify correction outcome rows before claim revisions are cutoff-filtered."""
    reader = CorrectionReader(operations.database, operations.clock)
    with closing(operations.database.connect()) as connection:
        rows = connection.execute(
            "SELECT DISTINCT review_id FROM corrections WHERE project=? AND revision<=? "
            "ORDER BY review_id",
            (project, revision_cutoff),
        ).fetchall()
    for row in rows:
        corrections = reader.list_corrections(
            str(row["review_id"]), revision_cutoff=revision_cutoff
        )
        for correction in corrections:
            _verify_correction_outcome_rows(operations, reader, correction)


def _verify_correction_outcome_rows(
    operations: ClaimOperations, reader: CorrectionReader, correction: StoredCorrection
) -> None:
    marker = '"correction_sha256":' + strict_dumps(correction.correction.receipt_sha256)
    authorization_json = strict_dumps(correction.authorization.model_dump(mode="json"))
    with closing(operations.database.connect()) as connection:
        rows = connection.execute(
            "SELECT * FROM claim_revisions WHERE project=? AND authorization_json=? "
            "AND instr(payload_json,?)>0",
            (correction.project, authorization_json, marker),
        ).fetchall()
    revisions = tuple(_claim_revision_from_row(row) for row in rows)
    decisions = correction.correction.decisions
    if len(revisions) != len(decisions):
        _raise_correction_outcome_integrity()
    for decision in decisions:
        payload = decision.model_dump(mode="json")
        matches = [
            revision
            for revision in revisions
            if revision.payload.get("decision") == payload
            and _correction_revision_matches(
                reader, revision, correction.authorization, correction
            )
        ]
        if len(matches) != 1:
            _raise_correction_outcome_integrity()


def _raise_correction_outcome_integrity() -> None:
    raise DataValidationError(
        "direct_memory_claim_revision_integrity",
        "Stored correction outcome claim revisions failed verification.",
    )
