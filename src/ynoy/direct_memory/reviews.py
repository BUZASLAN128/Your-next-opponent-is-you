from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import datetime
from typing import cast

from ynoy.correction import interaction_review_sha256
from ynoy.direct_memory.codec import (
    hash_json,
    strict_dumps,
    strict_loads,
)
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.ledger import append_revision_record
from ynoy.direct_memory.models import (
    FactProposal,
    ProvenanceState,
    RevisionKind,
    SourceEvent,
    StoredReview,
    UserAuthorizationReceipt,
)
from ynoy.direct_memory.source_authorship import SourceAuthorshipOperations
from ynoy.direct_memory.source_events import trusted_time
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError
from ynoy.interaction_review import build_interaction_review
from ynoy.models import InteractionReceipt, InteractionReview


class ReviewOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.clock = clock
        self.sources = SourceOperations(database, clock)
        self.attributions = SourceAuthorshipOperations(database, clock)

    def attribute_source_authorship(
        self,
        source_id: str,
        authorization: UserAuthorizationReceipt,
        *,
        expected_revision: int,
    ) -> int:
        return self.attributions.attribute_source_authorship(
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
        event = self.sources.get_source_event(source_id)
        self._bind_receipt(event, receipt)
        self.attributions.require_reviewable_source(event, receipt.subject_id)
        safe_claims = _validate_fact_claims(source_id, event.project, claims, self.sources)
        review = build_interaction_review(
            receipt,
            tuple(item.proposal for item in safe_claims),
            provider_evidence=None,
        )
        return self._persist_review(event, receipt, review, safe_claims, expected_revision)

    def _persist_review(
        self,
        event: SourceEvent,
        receipt: InteractionReceipt,
        review: InteractionReview,
        safe_claims: tuple[FactProposal, ...],
        expected_revision: int,
    ) -> StoredReview:
        digest = interaction_review_sha256(review)
        review_id = str(review.source.record_id)
        facts = _fact_links(safe_claims)
        with self.database.mutation(event.project, expected_revision) as (connection, revision):
            recorded_at = trusted_time(self.clock)
            connection.execute(
                "INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    event.project,
                    event.source_id,
                    strict_dumps(review.model_dump(mode="json")),
                    digest,
                    _facts_envelope(facts),
                    recorded_at.isoformat(),
                    revision,
                ),
            )
            for item in safe_claims:
                append_revision_record(
                    connection,
                    project=event.project,
                    fact_key=item.fact_key,
                    evidence_ids=item.evidence_ids,
                    state=ProvenanceState.PROPOSED,
                    kind=RevisionKind.ASSERTION,
                    payload=item.proposal.model_dump(mode="json"),
                    event_time=receipt.event_time,
                    recorded_at=recorded_at,
                    authorization=None,
                    tool_receipt_id=None,
                    related_fact_key=None,
                    revision=revision,
                )
        return StoredReview(
            review_id=review_id,
            project=event.project,
            source_id=event.source_id,
            review_sha256=digest,
            review=review,
            revision=revision,
        )

    def get_review(self, review_id: str) -> StoredReview:
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM reviews WHERE review_id=?", (review_id,)
            ).fetchone()
        if row is None:
            raise DataValidationError(
                "direct_memory_review_missing", "Direct-memory interaction review does not exist."
            )
        try:
            review = InteractionReview.model_validate(strict_loads(row["review_json"]))
            digest = interaction_review_sha256(review)
            if digest != row["review_sha256"] or str(review.source.record_id) != review_id:
                raise ValueError("review digest or identifier mismatch")
            event = self.sources.get_source_event(row["source_id"])
            if event.project != row["project"]:
                raise ValueError("review project does not match its source event")
            self._bind_receipt(event, review.source)
            self.attributions.require_reviewable_source(event, review.subject_id)
            return StoredReview(
                review_id=review_id,
                project=row["project"],
                source_id=row["source_id"],
                review_sha256=digest,
                review=review,
                revision=int(row["revision"]),
            )
        except Exception as exc:
            raise DataValidationError(
                "direct_memory_review_integrity", "Stored interaction review failed verification."
            ) from exc

    def review_facts(self, review_id: str) -> list[dict[str, object]]:
        stored = self.get_review(review_id)
        with closing(self.database.connect()) as connection:
            row = connection.execute(
                "SELECT facts_json FROM reviews WHERE review_id=?", (review_id,)
            ).fetchone()
        if row is None:
            raise DataValidationError(
                "direct_memory_review_missing", "Direct-memory interaction review does not exist."
            )
        value = strict_loads(row["facts_json"])
        if not isinstance(value, dict) or not isinstance(value.get("facts"), list):
            raise DataValidationError(
                "direct_memory_review_integrity", "Stored review fact links are invalid."
            )
        facts = value["facts"]
        if value.get("facts_sha256") != hash_json(facts):
            raise DataValidationError(
                "direct_memory_review_integrity",
                "Stored review fact links failed hash verification.",
            )
        _validate_fact_links(facts, stored)
        return cast(list[dict[str, object]], facts)

    @staticmethod
    def _bind_receipt(event: SourceEvent, receipt: InteractionReceipt) -> None:
        try:
            safe = InteractionReceipt.model_validate(receipt.model_dump(mode="python"))
        except Exception as exc:
            raise DataValidationError(
                "direct_memory_interaction_receipt_invalid",
                "Review requires a valid native YNOY receipt.",
            ) from exc
        source = safe
        if (
            source.response != event.exact_text
            or source.response_sha256 != event.sha256
            or source.conversation_id != event.project
            or source.turn_id != event.source_id
            or source.event_time != event.said_at
        ):
            raise DataValidationError(
                "direct_memory_interaction_receipt_mismatch",
                "Native interaction receipt must bind the exact stored source event.",
            )


def _revalidate_fact(value: FactProposal) -> FactProposal:
    if not isinstance(value, FactProposal):
        raise DataValidationError(
            "direct_memory_fact_proposal_required",
            "Direct-memory review accepts typed fact proposals.",
        )
    try:
        return FactProposal.model_validate(value.model_dump(mode="python"))
    except Exception as exc:
        raise DataValidationError(
            "direct_memory_fact_proposal_invalid", "Fact proposal failed strict validation."
        ) from exc


def _facts_envelope(facts: list[dict[str, object]]) -> str:
    return strict_dumps({"facts": facts, "facts_sha256": hash_json(facts)})


def _fact_links(claims: tuple[FactProposal, ...]) -> list[dict[str, object]]:
    return [
        {
            "claim_id": str(item.proposal.record_id),
            "fact_key": item.fact_key,
            "evidence_ids": list(item.evidence_ids),
        }
        for item in claims
    ]


def _validate_fact_links(facts: list[object], stored: StoredReview) -> None:
    claim_ids = {str(item.record_id) for item in stored.review.claims}
    linked_ids: set[str] = set()
    fact_keys: set[str] = set()
    for fact in facts:
        if not isinstance(fact, dict):
            raise DataValidationError(
                "direct_memory_review_integrity", "Stored review fact link is invalid."
            )
        claim_id, fact_key, evidence = (
            fact.get("claim_id"),
            fact.get("fact_key"),
            fact.get("evidence_ids"),
        )
        if (
            not isinstance(claim_id, str)
            or claim_id not in claim_ids
            or claim_id in linked_ids
            or not isinstance(fact_key, str)
            or not fact_key.strip()
            or fact_key in fact_keys
            or not isinstance(evidence, list)
            or not evidence
            or any(not isinstance(item, str) for item in evidence)
        ):
            raise DataValidationError(
                "direct_memory_review_integrity", "Stored review fact link failed validation."
            )
        linked_ids.add(claim_id)
        fact_keys.add(fact_key)
    if linked_ids != claim_ids:
        raise DataValidationError(
            "direct_memory_review_integrity", "Stored review fact links omit native claims."
        )


def _validate_fact_claims(
    source_id: str,
    project: str,
    claims: Sequence[FactProposal],
    sources: SourceOperations,
) -> tuple[FactProposal, ...]:
    safe_claims = tuple(_revalidate_fact(item) for item in claims)
    keys = {item.fact_key for item in safe_claims}
    if not safe_claims or len(keys) != len(safe_claims):
        raise DataValidationError(
            "direct_memory_fact_keys_invalid",
            "Review requires claims with unique stable fact keys.",
        )
    if any(source_id not in item.evidence_ids for item in safe_claims):
        raise DataValidationError(
            "direct_memory_evidence_missing",
            "Every proposal must cite its reviewed source event.",
        )
    for item in safe_claims:
        for evidence_id in item.evidence_ids:
            if sources.get_source_event(evidence_id).project != project:
                raise DataValidationError(
                    "direct_memory_evidence_project_mismatch",
                    "Fact evidence cannot cross project boundaries.",
                )
    return safe_claims
