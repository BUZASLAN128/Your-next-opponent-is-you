from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_TEXT, make_native_review
from ynoy.decision_brief import resolve_decision_brief
from ynoy.direct_memory import AuthorizationIntent, DirectMemoryStore, FactProposal
from ynoy.direct_memory.codec import correction_payload_sha256
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.errors import DataValidationError
from ynoy.interaction_review import build_interaction_review
from ynoy.models import ClaimModality, ConfirmClaimDecision, RejectClaimDecision, ScopeRef
from ynoy.review_replay import replay_interaction_review


def _store_review(store: DirectMemoryStore, source_id: str, record_id: int, negative: bool = False):
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=store.current_revision(PROJECT),
    )
    native = make_native_review(source_id=source_id)
    receipt = native.source.model_copy(update={"record_id": UUID(int=record_id)})
    claim = native.claims[0].model_copy(
        update={
            "record_id": UUID(int=record_id + 1),
            "receipt_id": receipt.record_id,
            "literal_normalization": "The user prefers concise answers.",
            "modality": ClaimModality.MUST_NOT if negative else ClaimModality.SHOULD,
        }
    )
    review = build_interaction_review(receipt, (claim,))
    return review, store.build_review(
        source_id,
        review.source,
        (
            FactProposal(
                fact_key="communication.concise",
                evidence_ids=(source_id,),
                proposal=claim,
            ),
        ),
        expected_revision=store.current_revision(PROJECT),
    )


def _correct(store: DirectMemoryStore, review, stored, source_id: str, decision) -> object:
    decisions = (decision,)
    operation = "correct"
    digest = correction_payload_sha256(decisions, operation=operation)
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=f"Authorize native correction {source_id}.",
        authorization_intent=AuthorizationIntent(
            action=operation,
            payload_sha256=digest,
            subject_id="self",
            review_sha256=stored.review_sha256,
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        source_id,
        action=operation,
        payload_sha256=digest,
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    return store.apply_correction(
        stored.review_id,
        decisions,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
        operation=operation,
    )


def _assert_temporal_prefixes(store, review, history) -> None:
    as_of_limited = store.brief(
        PROJECT,
        as_of=NOW + timedelta(days=3),
        known_at=NOW + timedelta(days=8),
    )
    knowledge_limited = store.brief(
        PROJECT,
        as_of=NOW + timedelta(days=8),
        known_at=NOW + timedelta(days=3),
    )
    scope = ScopeRef(person_id="self", project=PROJECT)
    full_state = replay_interaction_review(review, tuple(item.correction for item in history))
    known_prefix_state = replay_interaction_review(
        review, tuple(item.correction for item in history[:2])
    )
    full_native = resolve_decision_brief(full_state, scope, NOW + timedelta(days=3))
    known_prefix_native = resolve_decision_brief(known_prefix_state, scope, NOW + timedelta(days=8))
    assert as_of_limited.native_briefs == (full_native,)
    assert knowledge_limited.native_briefs == (known_prefix_native,)
    assert as_of_limited.source_events[0].sha256 == knowledge_limited.source_events[0].sha256


def test_native_correction_history_preserves_x_y_x_ids_and_temporal_prefix(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: clock[0], data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    review, stored = _store_review(store, "history-source", 8200)
    claim_id = review.claims[0].record_id
    first = _correct(
        store,
        review,
        stored,
        "history-auth-x1",
        ConfirmClaimDecision(claim_id=claim_id, subject_id="self"),
    )
    clock[0] = NOW + timedelta(days=2)
    second = _correct(
        store,
        review,
        stored,
        "history-auth-y",
        RejectClaimDecision(claim_id=claim_id, subject_id="self", reason="Synthetic reversal."),
    )
    clock[0] = NOW + timedelta(days=4)
    third = _correct(
        store,
        review,
        stored,
        "history-auth-x2",
        ConfirmClaimDecision(claim_id=claim_id, subject_id="self"),
    )
    history = store.list_corrections(stored.review_id)
    assert tuple(item.correction.record_id for item in history) == (
        first.correction.record_id,
        second.correction.record_id,
        third.correction.record_id,
    )
    _assert_temporal_prefixes(store, review, history)
    assert store.get_review(stored.review_id).review_sha256 == stored.review_sha256


def test_cross_review_conflicts_are_preserved_and_brief_abstains(tmp_path: Path) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    positive, positive_row = _store_review(store, "conflict-positive", 8300)
    negative, negative_row = _store_review(store, "conflict-negative", 8400, negative=True)
    _correct(
        store,
        positive,
        positive_row,
        "conflict-auth-positive",
        ConfirmClaimDecision(claim_id=positive.claims[0].record_id, subject_id="self"),
    )
    _correct(
        store,
        negative,
        negative_row,
        "conflict-auth-negative",
        ConfirmClaimDecision(claim_id=negative.claims[0].record_id, subject_id="self"),
    )

    brief = store.brief(PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW + timedelta(days=1))
    assert len(brief.native_briefs) == 2
    assert brief.unresolved_conflicts == (("communication.concise", "communication.concise"),)
    assert brief.abstained
    assert "unresolved_conflict" in brief.abstention_reasons
    assert brief.authority == "none" and not brief.automatic_core_promotion


def test_one_live_authorization_cannot_be_consumed_twice(tmp_path: Path) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    review, stored = _store_review(store, "one-use-source", 8500)
    decision = ConfirmClaimDecision(claim_id=review.claims[0].record_id, subject_id="self")
    correction = _correct(store, review, stored, "one-use-auth", decision)

    with pytest.raises(DataValidationError) as replayed:
        store.apply_correction(
            stored.review_id,
            (decision,),
            authorization=correction.authorization,
            expected_revision=store.current_revision(PROJECT),
        )
    assert replayed.value.code == "direct_memory_authorization_required"


def test_late_known_rejection_changes_retrospective_brief_without_source_rewrite(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: clock[0], data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    review, stored = _store_review(store, "retrospective-source", 8600)
    source_hash = store.get_source_event("retrospective-source").sha256
    claim_id = review.claims[0].record_id
    first = _correct(
        store,
        review,
        stored,
        "retrospective-auth-confirm",
        ConfirmClaimDecision(claim_id=claim_id, subject_id="self"),
    )
    clock[0] = NOW + timedelta(days=2)
    rejected = _correct(
        store,
        review,
        stored,
        "retrospective-auth-reject",
        RejectClaimDecision(claim_id=claim_id, subject_id="self", reason="Later correction."),
    )

    earlier_knowledge = store.brief(
        PROJECT,
        as_of=NOW + timedelta(days=1),
        known_at=NOW + timedelta(days=1),
    )
    later_knowledge = store.brief(
        PROJECT,
        as_of=NOW + timedelta(days=1),
        known_at=NOW + timedelta(days=3),
    )
    scope = ScopeRef(person_id="self", project=PROJECT)
    expected_first = resolve_decision_brief(first.state, scope, NOW + timedelta(days=1))
    expected_rejection = resolve_decision_brief(rejected.state, scope, NOW + timedelta(days=1))
    assert earlier_knowledge.native_briefs == (expected_first,)
    assert later_knowledge.native_briefs == (expected_rejection,)
    assert store.get_source_event("retrospective-source").sha256 == source_hash
    assert store.get_review(stored.review_id).review_sha256 == stored.review_sha256
