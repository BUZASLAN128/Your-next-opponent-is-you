from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

from ynoy.direct_memory.codec import claim_revision_payload_sha256, strict_dumps, strict_loads
from ynoy.direct_memory.models import (
    ClaimRevision,
    ProvenanceState,
    RevisionKind,
    StoredCorrection,
    UserAuthorizationReceipt,
)
from ynoy.errors import DataValidationError

if TYPE_CHECKING:
    from ynoy.direct_memory.claims import ClaimOperations
    from ynoy.direct_memory.correction_reader import CorrectionReader


@dataclass(frozen=True, slots=True)
class PayloadSnapshot:
    canonical_json: str

    def materialize(self) -> dict[str, object]:
        value = strict_loads(self.canonical_json)
        if not isinstance(value, dict):
            raise DataValidationError(
                "direct_memory_json_invalid", "Claim revision payload must be a JSON object."
            )
        return value

    def digest_for_claim_revision(
        self,
        *,
        fact_key: str,
        evidence_ids: tuple[str, ...],
        state: ProvenanceState,
        kind: RevisionKind,
        event_time: datetime | None,
        tool_receipt_id: str | None,
        related_fact_key: str | None = None,
    ) -> str:
        return claim_revision_payload_sha256(
            fact_key=fact_key,
            evidence_ids=evidence_ids,
            state=state,
            kind=kind,
            payload=self.materialize(),
            event_time=event_time,
            tool_receipt_id=tool_receipt_id,
            related_fact_key=related_fact_key,
        )


def snapshot_payload(payload: Mapping[str, object]) -> PayloadSnapshot:
    encoded = strict_dumps(payload)
    value = strict_loads(encoded)
    if not isinstance(value, dict):
        raise DataValidationError(
            "direct_memory_json_invalid", "Claim revision payload must be a JSON object."
        )
    return PayloadSnapshot(encoded)


def manual_claim_state(value: ProvenanceState) -> ProvenanceState:
    safe_state = ProvenanceState(value)
    if safe_state in {
        ProvenanceState.PROPOSED,
        ProvenanceState.ACCEPTED,
        ProvenanceState.REJECTED,
        ProvenanceState.CORRECTED,
    }:
        raise DataValidationError(
            "direct_memory_native_review_required",
            "Proposal and review outcomes must use the existing YNOY review lifecycle.",
        )
    return safe_state


def tool_result_has_negative_outcome(result: Mapping[str, object]) -> bool:
    """Check only documented top-level completion fields in persisted tool results."""
    if result.get("executed") is False:
        return True
    if result.get("cancelled") is True or result.get("canceled") is True:
        return True
    status = result.get("status")
    return isinstance(status, str) and status.strip().casefold() in {
        "canceled",
        "cancelled",
        "failed",
        "aborted",
    }


def verify_revision_sources(
    operations: ClaimOperations, revisions: Sequence[ClaimRevision]
) -> None:
    for revision in revisions:
        _verify_revision_authorization(operations, revision)
        for source_id in revision.evidence_ids:
            if operations.sources.get_source_event(source_id).project != revision.project:
                raise DataValidationError(
                    "direct_memory_claim_revision_integrity",
                    "Stored claim evidence source belongs to another project.",
                )
        if revision.state == ProvenanceState.TOOL_VERIFIED:
            _verify_tool_revision(operations, revision)


def _verify_tool_revision(operations: ClaimOperations, revision: ClaimRevision) -> None:
    receipt = operations._tool_receipt(revision.tool_receipt_id)
    if (
        receipt is None
        or receipt.project != revision.project
        or receipt.tool_receipt_id not in revision.evidence_ids
    ):
        raise DataValidationError(
            "direct_memory_claim_revision_integrity",
            "Stored tool-verified claim has no valid tool result.",
        )
    if tool_result_has_negative_outcome(receipt.result):
        raise DataValidationError(
            "direct_memory_tool_result_contradiction",
            "Stored tool result explicitly records a failed or cancelled operation.",
        )
    if strict_dumps(revision.payload) != strict_dumps(receipt.result):
        raise DataValidationError(
            "direct_memory_tool_result_mismatch",
            "Stored tool-verified claim does not match its persisted tool result.",
        )


def _verify_revision_authorization(operations: ClaimOperations, revision: ClaimRevision) -> None:
    authorization = revision.authorization
    if authorization is None:
        return
    try:
        if authorization.action == "claim_revision":
            _verify_manual_revision_authorization(operations, revision, authorization)
        else:
            _verify_correction_revision_authorization(operations, revision, authorization)
    except Exception as exc:
        raise DataValidationError(
            "direct_memory_claim_revision_integrity",
            "Stored claim revision authorization failed verification.",
        ) from exc


def _verify_manual_revision_authorization(
    operations: ClaimOperations,
    revision: ClaimRevision,
    authorization: UserAuthorizationReceipt,
) -> None:
    event = operations.sources.verify_authorization(
        authorization,
        action="claim_revision",
        payload_sha256=_revision_digest(revision),
        subject_id=authorization.subject_id,
        review_sha256=None,
        allow_consumed=True,
    )
    if event.project != revision.project:
        raise ValueError("authorization project does not match claim revision")


def _revision_digest(revision: ClaimRevision) -> str:
    return claim_revision_payload_sha256(
        fact_key=revision.fact_key,
        evidence_ids=revision.evidence_ids,
        state=revision.state,
        kind=revision.kind,
        payload=revision.payload,
        event_time=revision.event_time,
        tool_receipt_id=revision.tool_receipt_id,
        related_fact_key=revision.related_fact_key,
    )


def _verify_correction_revision_authorization(
    operations: ClaimOperations,
    revision: ClaimRevision,
    authorization: UserAuthorizationReceipt,
) -> None:
    from ynoy.direct_memory.correction_reader import CorrectionReader

    reader = CorrectionReader(operations.database, operations.clock)
    with closing(operations.database.connect()) as connection:
        rows = connection.execute(
            "SELECT DISTINCT review_id FROM corrections WHERE project=? ORDER BY review_id",
            (revision.project,),
        ).fetchall()
    for row in rows:
        records = reader.list_corrections(str(row["review_id"]))
        if any(
            _correction_revision_matches(reader, revision, authorization, item) for item in records
        ):
            return
    raise ValueError("claim revision does not match a verified correction record")


def _correction_revision_matches(
    reader: CorrectionReader,
    revision: ClaimRevision,
    authorization: UserAuthorizationReceipt,
    correction: StoredCorrection,
) -> bool:
    payload = revision.payload
    if (
        correction.project != revision.project
        or correction.authorization != authorization
        or correction.operation != authorization.action
        or correction.correction.receipt_sha256 != payload.get("correction_sha256")
        or correction.correction.review_sha256 != payload.get("review_sha256")
        or payload.get("operation") != authorization.action
    ):
        return False
    decision_payload = payload.get("decision")
    decisions = [
        item
        for item in correction.correction.decisions
        if item.model_dump(mode="json") == decision_payload
    ]
    if len(decisions) != 1:
        return False
    links = reader.reviews.review_facts(correction.review_id)
    claim_id = str(decisions[0].claim_id)
    link = next((item for item in links if item["claim_id"] == claim_id), None)
    return bool(
        link is not None
        and link["fact_key"] == revision.fact_key
        and tuple(cast(list[str], link["evidence_ids"])) == revision.evidence_ids
    )


__all__ = [
    "PayloadSnapshot",
    "manual_claim_state",
    "snapshot_payload",
    "tool_result_has_negative_outcome",
    "verify_revision_sources",
]
