from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import UUID

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_TEXT, make_native_review
from ynoy.decision_brief import resolve_decision_brief
from ynoy.direct_memory import (
    AuthorizationIntent,
    DirectMemoryStore,
    FactProposal,
    StoredCorrection,
    StoredReview,
)
from ynoy.direct_memory.codec import correction_payload_sha256
from ynoy.direct_memory.models import UserAuthorizationReceipt
from ynoy.interaction_review import build_interaction_review
from ynoy.models import (
    ClaimReviewDecision,
    ConfirmClaimDecision,
    InteractionReview,
    RejectClaimDecision,
    ScopeRef,
)
from ynoy.util import canonical_sha256


def _authorize_decisions(
    store: DirectMemoryStore, review_sha256: str, source_id: str, decisions: tuple[object, ...]
) -> UserAuthorizationReceipt:
    digest = canonical_sha256([item.model_dump(mode="json") for item in decisions])
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=f"Explicitly authorize {source_id}.",
        authorization_intent=AuthorizationIntent(
            action="correct",
            payload_sha256=digest,
            subject_id="self",
            review_sha256=review_sha256,
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    return store.authorize_action(
        source_id,
        action="correct",
        payload_sha256=digest,
        subject_id="self",
        review_sha256=review_sha256,
    )


def _two_fact_review(store: DirectMemoryStore) -> tuple[InteractionReview, StoredReview]:
    native = make_native_review()
    source_id = native.source.turn_id
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=0,
    )
    unchanged = native.claims[0].model_copy(
        update={
            "record_id": UUID(int=8104),
            "literal_normalization": "The user prefers a concise format.",
        }
    )
    review = build_interaction_review(native.source, (*native.claims, unchanged))
    stored = store.build_review(
        source_id,
        review.source,
        tuple(
            FactProposal(fact_key=key, evidence_ids=(source_id,), proposal=claim)
            for key, claim in zip(
                ("communication.concise", "communication.format"), review.claims, strict=True
            )
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    return review, stored


def _apply(
    store: DirectMemoryStore,
    review: StoredReview,
    source_id: str,
    decisions: tuple[ClaimReviewDecision, ...],
) -> StoredCorrection:
    authorization = _authorize_decisions(store, review.review_sha256, source_id, decisions)
    return store.apply_correction(
        review.review_id,
        decisions,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
    )


def test_later_partial_rejection_leaves_other_confirmed_fact_visible(
    tmp_path: Path,
) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    review, stored = _two_fact_review(store)
    confirm_both = (
        ConfirmClaimDecision(claim_id=review.claims[0].record_id, subject_id="self"),
        ConfirmClaimDecision(claim_id=review.claims[1].record_id, subject_id="self"),
    )
    first = _apply(store, stored, "auth-confirm-both", confirm_both)
    reject_one = (
        RejectClaimDecision(
            claim_id=review.claims[0].record_id,
            subject_id="self",
            reason="Withdraw the first synthetic fact.",
        ),
    )
    second = _apply(store, stored, "auth-reject-one", reject_one)
    assert first.state.state_sha256 != second.state.state_sha256

    as_of = NOW + timedelta(days=1)
    brief = store.brief(PROJECT, as_of=as_of, known_at=as_of)
    native_brief = resolve_decision_brief(
        second.state, ScopeRef(person_id="self", project=PROJECT), as_of
    )
    assert brief.native_briefs == (native_brief,)
    assert tuple(item.claim_id for item in native_brief.persona_candidates) == (
        review.claims[1].record_id,
    )
    assert review.claims[0].record_id not in {
        item.claim_id for item in native_brief.all_entries()
    }

    reopened = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    assert reopened.brief(PROJECT, as_of=as_of, known_at=as_of) == brief


def test_supersession_binds_mapping_and_persists_native_fact_relation(tmp_path: Path) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    review, stored = _two_fact_review(store)
    decisions = (
        RejectClaimDecision(
            claim_id=review.claims[0].record_id,
            subject_id="self",
            reason="Replace the first synthetic fact.",
        ),
    )
    mapping = {"communication.concise": "communication.format"}
    digest = correction_payload_sha256(decisions, operation="supersede", supersessions=mapping)
    store.record_live_user_input(
        source_id="auth-supersede-one",
        project=PROJECT,
        said_at=NOW,
        exact_text="Authorize this synthetic supersession.",
        authorization_intent=AuthorizationIntent(
            action="supersede",
            payload_sha256=digest,
            subject_id="self",
            review_sha256=stored.review_sha256,
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        "auth-supersede-one",
        action="supersede",
        payload_sha256=digest,
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    result = store.apply_correction(
        stored.review_id,
        decisions,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
        operation="supersede",
        supersessions=mapping,
    )

    replaced = [
        item
        for item in store.list_claim_revisions(PROJECT)
        if item.fact_key == "communication.concise"
    ]
    assert result.operation == "supersede"
    assert result.supersessions == mapping
    assert replaced[-1].related_fact_key == "communication.format"
