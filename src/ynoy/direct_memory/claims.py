from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import datetime

from ynoy.direct_memory.codec import strict_dumps, strict_loads
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
from ynoy.direct_memory.payload_snapshot import (
    PayloadSnapshot,
    manual_claim_state,
    snapshot_payload,
    tool_result_has_negative_outcome,
    verify_revision_sources,
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
        state = manual_claim_state(state)
        evidence = self._project_evidence(project, evidence_ids)
        snapshot = snapshot_payload(payload)
        self._check_tool_binding(project, state, tool_receipt_id, evidence, snapshot)
        digest = snapshot.digest_for_claim_revision(
            fact_key=fact_key,
            evidence_ids=evidence,
            state=state,
            kind=RevisionKind.ASSERTION,
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
            state,
            snapshot,
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

    def _check_tool_binding(
        self,
        project: str,
        state: ProvenanceState,
        receipt_id: str | None,
        evidence: tuple[str, ...],
        payload: PayloadSnapshot,
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
            and payload.canonical_json != strict_dumps(receipt.result)
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
        payload: PayloadSnapshot,
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
                payload=payload.materialize(),
                payload_json=payload.canonical_json,
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
        verify_revision_sources(self, revisions)
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
