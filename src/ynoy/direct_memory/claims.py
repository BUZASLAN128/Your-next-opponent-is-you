from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import datetime

from ynoy.direct_memory.codec import claim_revision_payload_sha256, strict_dumps, strict_loads
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.ledger import append_revision_record, load_claim_revisions
from ynoy.direct_memory.models import (
    ClaimRevision,
    ProvenanceState,
    RevisionKind,
    SourceType,
    ToolReceipt,
    UserAuthorizationReceipt,
)
from ynoy.direct_memory.source_events import trusted_time
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError


class ClaimOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock
        self.sources = SourceOperations(database, clock)

    def append_claim_revision(
        self,
        *,
        project: str,
        fact_key: str,
        evidence_ids: Sequence[str],
        state: ProvenanceState,
        payload: Mapping[str, object],
        authorization: UserAuthorizationReceipt,
        expected_revision: int,
        event_time: datetime | None = None,
        tool_receipt_id: str | None = None,
        subject_id: str = "self",
    ) -> ClaimRevision:
        safe_state = _manual_state(state)
        evidence = self._project_evidence(project, evidence_ids)
        self._validate_tool_binding(project, safe_state, tool_receipt_id, evidence, payload)
        digest = claim_revision_payload_sha256(
            fact_key=fact_key,
            evidence_ids=evidence,
            state=safe_state,
            kind=RevisionKind.ASSERTION,
            payload=payload,
            event_time=event_time,
            tool_receipt_id=tool_receipt_id,
        )
        live_event = self.sources.verify_authorization(
            authorization,
            action="claim_revision",
            payload_sha256=digest,
            subject_id=subject_id,
            review_sha256=None,
        )
        if live_event.project != project:
            raise DataValidationError(
                "direct_memory_authorization_mismatch",
                "Claim revision authorization belongs to another project.",
            )
        return self._persist_claim(
            project,
            fact_key,
            evidence,
            safe_state,
            payload,
            authorization,
            expected_revision,
            event_time,
            tool_receipt_id,
        )

    def _project_evidence(self, project: str, evidence_ids: Sequence[str]) -> tuple[str, ...]:
        evidence = tuple(evidence_ids)
        if not evidence or len(set(evidence)) != len(evidence):
            raise DataValidationError(
                "direct_memory_evidence_invalid",
                "Claim evidence identifiers must be unique and non-empty.",
            )
        if any(self.sources.get_source_event(item).project != project for item in evidence):
            raise DataValidationError(
                "direct_memory_evidence_project_mismatch",
                "Claim evidence cannot cross project boundaries.",
            )
        return evidence

    def _validate_tool_binding(
        self,
        project: str,
        state: ProvenanceState,
        receipt_id: str | None,
        evidence: tuple[str, ...],
        payload: Mapping[str, object],
    ) -> None:
        receipt = self._tool_receipt(receipt_id) if receipt_id else None
        if state == ProvenanceState.TOOL_VERIFIED and (
            receipt is None or receipt.project != project or receipt.tool_receipt_id not in evidence
        ):
            raise DataValidationError(
                "direct_memory_tool_evidence_required",
                "Tool-verified claims require a persisted tool receipt in their evidence.",
            )
        if (
            state == ProvenanceState.TOOL_VERIFIED
            and receipt is not None
            and tool_result_has_negative_outcome(receipt.result)
        ):
            raise DataValidationError(
                "direct_memory_tool_result_contradiction",
                "Tool result explicitly records a failed or cancelled operation.",
            )
        if (
            state == ProvenanceState.TOOL_VERIFIED
            and receipt is not None
            and strict_dumps(payload) != strict_dumps(receipt.result)
        ):
            raise DataValidationError(
                "direct_memory_tool_result_mismatch",
                "Tool-verified claim payload must exactly match its persisted tool result.",
            )
        if state != ProvenanceState.TOOL_VERIFIED and receipt_id is not None:
            raise DataValidationError(
                "direct_memory_tool_evidence_state",
                "Only tool-verified claims may bind a tool receipt.",
            )

    def _persist_claim(
        self,
        project: str,
        fact_key: str,
        evidence: tuple[str, ...],
        state: ProvenanceState,
        payload: Mapping[str, object],
        authorization: UserAuthorizationReceipt,
        expected_revision: int,
        event_time: datetime | None,
        tool_receipt_id: str | None,
    ) -> ClaimRevision:
        with self.database.mutation(project, expected_revision) as (connection, revision):
            recorded_at = trusted_time(self.clock)
            self.sources.consume_authorization(
                connection,
                authorization,
                project=project,
                revision=revision,
                recorded_at=recorded_at,
            )
            return append_revision_record(
                connection,
                project=project,
                fact_key=fact_key,
                evidence_ids=evidence,
                state=state,
                kind=RevisionKind.ASSERTION,
                payload=payload,
                event_time=event_time,
                recorded_at=recorded_at,
                authorization=authorization,
                tool_receipt_id=tool_receipt_id,
                related_fact_key=None,
                revision=revision,
            )

    def list_claim_revisions(
        self,
        project: str,
        *,
        known_at: datetime | None = None,
        as_of: datetime | None = None,
    ) -> tuple[ClaimRevision, ...]:
        with closing(self.database.connect()) as connection:
            revisions = load_claim_revisions(
                connection, project=project, known_at=known_at, as_of=as_of
            )
        _verify_revision_sources(self, revisions)
        return revisions

    def _tool_receipt(self, receipt_id: str | None) -> ToolReceipt | None:
        if receipt_id is None:
            return None
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM tool_receipts WHERE tool_receipt_id=?", (receipt_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            event = self.sources.get_source_event(row["source_id"])
            result = strict_loads(row["result_json"])
            if not isinstance(result, dict) or event.source_type != SourceType.TOOL_RESULT:
                raise ValueError("tool result source type mismatch")
            value = ToolReceipt(
                tool_receipt_id=row["tool_receipt_id"],
                project=row["project"],
                tool_name=row["tool_name"],
                operation=row["operation"],
                input_sha256=row["input_sha256"],
                result=result,
                result_sha256=row["result_sha256"],
                recorded_at=row["recorded_at"],
                revision=row["revision"],
            )
            if value.project != event.project or event.exact_text != strict_dumps(result):
                raise ValueError("tool receipt source binding mismatch")
            return value
        except Exception as exc:
            raise DataValidationError(
                "direct_memory_tool_receipt_integrity", "Stored tool receipt failed verification."
            ) from exc


__all__ = ["ClaimOperations"]


def _manual_state(value: ProvenanceState) -> ProvenanceState:
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


def _verify_revision_sources(
    operations: ClaimOperations, revisions: Sequence[ClaimRevision]
) -> None:
    for revision in revisions:
        for source_id in revision.evidence_ids:
            if operations.sources.get_source_event(source_id).project != revision.project:
                raise DataValidationError(
                    "direct_memory_claim_revision_integrity",
                    "Stored claim evidence source belongs to another project.",
                )
        if revision.state == ProvenanceState.TOOL_VERIFIED:
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
