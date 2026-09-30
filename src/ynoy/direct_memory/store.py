from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from ynoy.direct_memory.briefing import BriefOperations
from ynoy.direct_memory.claims import ClaimOperations
from ynoy.direct_memory.corrections import CorrectionOperations
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.exporting import ExportOperations
from ynoy.direct_memory.models import (
    AuthorizationIntent,
    ClaimRevision,
    DirectMemoryBrief,
    FactProposal,
    ProvenanceState,
    SourceEvent,
    StoredCorrection,
    StoredReview,
    ToolReceipt,
    UserAuthorizationReceipt,
)
from ynoy.direct_memory.reviews import ReviewOperations
from ynoy.direct_memory.sources import SourceOperations
from ynoy.models import ClaimReviewDecision, InteractionReceipt, Speaker
from ynoy.util import utc_now


class DirectMemoryStore:
    def __init__(
        self,
        path: Path,
        *,
        data_plane: DataPlane = DataPlane.PRIVATE,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.database = DirectMemoryDatabase(path, data_plane=data_plane)
        self.clock = clock
        self.sources = SourceOperations(self.database, clock)
        self.reviews = ReviewOperations(self.database, clock)
        self.corrections = CorrectionOperations(self.database, clock)
        self.claims = ClaimOperations(self.database, clock)
        self.briefs = BriefOperations(self.database, clock)
        self.exports = ExportOperations(self.database, clock)

    def current_revision(self, project: str) -> int:
        return self.sources.current_revision(project)

    def record_source_event(
        self,
        *,
        source_id: str,
        project: str,
        speaker: Speaker | str,
        said_at: datetime | None,
        exact_text: str,
        expected_revision: int,
    ) -> SourceEvent:
        return self.sources.record_source_event(
            source_id=source_id,
            project=project,
            speaker=speaker,
            said_at=said_at,
            exact_text=exact_text,
            expected_revision=expected_revision,
        )

    def record_live_user_input(
        self,
        *,
        source_id: str,
        project: str,
        said_at: datetime | None,
        exact_text: str,
        expected_revision: int,
        authorization_intent: AuthorizationIntent | None = None,
        subject_id: str = "self",
    ) -> SourceEvent:
        return self.sources.record_live_user_input(
            source_id=source_id,
            project=project,
            said_at=said_at,
            exact_text=exact_text,
            expected_revision=expected_revision,
            authorization_intent=authorization_intent,
            subject_id=subject_id,
        )

    def record_tool_result(
        self,
        *,
        source_id: str,
        project: str,
        tool_name: str,
        operation: str,
        inputs: Mapping[str, object],
        result: Mapping[str, object],
        expected_revision: int,
    ) -> ToolReceipt:
        return self.sources.record_tool_result(
            source_id=source_id,
            project=project,
            tool_name=tool_name,
            operation=operation,
            inputs=inputs,
            result=result,
            expected_revision=expected_revision,
        )

    def get_source_event(self, source_id: str) -> SourceEvent:
        return self.sources.get_source_event(source_id)

    def authorize_action(
        self,
        live_user_source_id: str,
        *,
        action: str,
        payload_sha256: str,
        subject_id: str,
        review_sha256: str | None = None,
    ) -> UserAuthorizationReceipt:
        return self.sources.authorize_action(
            live_user_source_id,
            action=action,
            payload_sha256=payload_sha256,
            subject_id=subject_id,
            review_sha256=review_sha256,
        )

    def attribute_source_authorship(
        self,
        source_id: str,
        authorization: UserAuthorizationReceipt,
        *,
        expected_revision: int,
    ) -> int:
        return self.reviews.attribute_source_authorship(
            source_id, authorization, expected_revision=expected_revision
        )

    def build_review(
        self,
        source_id: str,
        receipt: InteractionReceipt,
        claims: Sequence[FactProposal],
        *,
        expected_revision: int,
    ) -> StoredReview:
        return self.reviews.build_review(
            source_id, receipt, claims, expected_revision=expected_revision
        )

    def get_review(self, review_id: str) -> StoredReview:
        return self.reviews.get_review(review_id)

    def list_corrections(self, review_id: str) -> tuple[StoredCorrection, ...]:
        return self.corrections.list_corrections(review_id)

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
        return self.corrections.apply_correction(
            review_id,
            decisions,
            authorization,
            expected_revision=expected_revision,
            operation=operation,
            supersessions=supersessions,
        )

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
        return self.claims.append_claim_revision(
            project=project,
            fact_key=fact_key,
            evidence_ids=evidence_ids,
            state=state,
            payload=payload,
            authorization=authorization,
            expected_revision=expected_revision,
            event_time=event_time,
            tool_receipt_id=tool_receipt_id,
            subject_id=subject_id,
        )

    def list_claim_revisions(
        self,
        project: str,
        *,
        known_at: datetime | None = None,
        as_of: datetime | None = None,
    ) -> tuple[ClaimRevision, ...]:
        return self.claims.list_claim_revisions(project, known_at=known_at, as_of=as_of)

    def brief(self, project: str, *, as_of: datetime, known_at: datetime) -> DirectMemoryBrief:
        return self.briefs.brief(project, as_of=as_of, known_at=known_at)

    def export_jsonl(self, project: str | None = None) -> str:
        return self.exports.export_jsonl(project)

    def backup(self, destination: Path) -> Path:
        return self.database.backup(destination)
