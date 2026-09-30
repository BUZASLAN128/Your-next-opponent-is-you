from __future__ import annotations

import socket
from datetime import timedelta
from pathlib import Path

import pytest

from tests.direct_memory_fixtures import (
    CLAIM_ID,
    NOW,
    PROJECT,
    SOURCE_ID,
    SOURCE_TEXT,
    make_native_review,
)
from ynoy.correction import interaction_review_sha256
from ynoy.decision_brief import resolve_decision_brief
from ynoy.direct_memory import (
    AuthorizationIntent,
    DirectMemoryStore,
    FactProposal,
    StoredCorrection,
    StoredReview,
    source_authorship_payload_sha256,
)
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.errors import DataValidationError
from ynoy.models import ConfirmClaimDecision, ScopeRef, Speaker
from ynoy.reasoner import LocalOpenAIReasoner
from ynoy.util import canonical_sha256

SYNTHETIC_PLANE = DataPlane.PUBLIC_SYNTHETIC


def _decision_digest(decisions: tuple[ConfirmClaimDecision, ...]) -> str:
    return canonical_sha256([item.model_dump(mode="json") for item in decisions])


def _stored_review(store: DirectMemoryStore):
    store.record_live_user_input(
        source_id=SOURCE_ID,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=store.current_revision(PROJECT),
    )
    review = make_native_review()
    return store.build_review(
        source_id=SOURCE_ID,
        receipt=review.source,
        claims=(
            FactProposal(
                fact_key="communication.concise",
                evidence_ids=(SOURCE_ID,),
                proposal=review.claims[0],
            ),
        ),
        expected_revision=store.current_revision(PROJECT),
    )


def test_explicit_correction_survives_sqlite_reload_with_native_brief_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("direct-memory operations must not invoke a model or network call")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(LocalOpenAIReasoner, "complete", forbidden)
    path = tmp_path / "memory.sqlite3"
    store = DirectMemoryStore(path, clock=lambda: NOW, data_plane=SYNTHETIC_PLANE)
    stored = _stored_review(store)
    correction = _confirm_native_review(store, stored)
    as_of = NOW + timedelta(days=1)
    brief = store.brief(PROJECT, as_of=as_of, known_at=as_of)
    native = resolve_decision_brief(
        correction.state, ScopeRef(person_id="self", project=PROJECT), as_of
    )

    assert brief.native_briefs == (native,)
    assert (
        correction.correction.receipt_sha256
        in brief.native_briefs[0].used_correction_receipt_hashes
    )
    assert brief.authority == "none" and not brief.automatic_core_promotion

    reopened = DirectMemoryStore(path, clock=lambda: NOW, data_plane=SYNTHETIC_PLANE)
    reloaded = reopened.brief(PROJECT, as_of=as_of, known_at=as_of)
    assert reloaded == brief
    assert reopened.current_revision(PROJECT) == store.current_revision(PROJECT)


def _confirm_native_review(store: DirectMemoryStore, stored: StoredReview) -> StoredCorrection:
    decisions = (ConfirmClaimDecision(claim_id=CLAIM_ID, subject_id="self"),)
    intent = AuthorizationIntent(
        action="correct",
        payload_sha256=_decision_digest(decisions),
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    store.record_live_user_input(
        source_id="live-correction",
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        authorization_intent=intent,
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        "live-correction",
        action="correct",
        payload_sha256=_decision_digest(decisions),
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    correction = store.apply_correction(
        stored.review_id,
        decisions,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
    )
    return correction


def test_imported_or_unbound_user_text_cannot_authorize_correction(tmp_path: Path) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=SYNTHETIC_PLANE
    )
    stored = _stored_review(store)
    decisions = (ConfirmClaimDecision(claim_id=CLAIM_ID, subject_id="self"),)
    digest = _decision_digest(decisions)

    store.record_source_event(
        source_id="imported-user",
        project=PROJECT,
        speaker=Speaker.USER,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=store.current_revision(PROJECT),
    )
    imported_review = make_native_review(source_id="imported-user")
    with pytest.raises(DataValidationError) as attribution:
        store.build_review(
            "imported-user",
            imported_review.source,
            (
                FactProposal(
                    fact_key="communication.imported",
                    evidence_ids=("imported-user",),
                    proposal=imported_review.claims[0],
                ),
            ),
            expected_revision=store.current_revision(PROJECT),
        )
    assert attribution.value.code == "direct_memory_attribution_required"
    store.record_live_user_input(
        source_id="live-unbound",
        project=PROJECT,
        said_at=NOW,
        exact_text="hello",
        expected_revision=store.current_revision(PROJECT),
    )

    for source_id in ("imported-user", "live-unbound"):
        with pytest.raises(DataValidationError) as blocked:
            store.authorize_action(
                source_id,
                action="correct",
                payload_sha256=digest,
                subject_id="self",
                review_sha256=stored.review_sha256,
            )
        assert blocked.value.code == "direct_memory_authorization_required"


def test_date_only_native_source_precision_survives_fresh_reload(tmp_path: Path) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=SYNTHETIC_PLANE
    )
    event_time = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    store.record_live_user_input(
        source_id=SOURCE_ID,
        project=PROJECT,
        said_at=event_time,
        exact_text=SOURCE_TEXT,
        expected_revision=0,
    )
    review = make_native_review(event_time=event_time, event_time_precision="date_only")
    stored = store.build_review(
        SOURCE_ID,
        review.source,
        (
            FactProposal(
                fact_key="communication.concise",
                evidence_ids=(SOURCE_ID,),
                proposal=review.claims[0],
            ),
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    reloaded = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=SYNTHETIC_PLANE
    ).get_review(stored.review_id)
    assert reloaded.review == review
    assert reloaded.review.source.event_time_precision == "date_only"
    assert reloaded.review_sha256 == interaction_review_sha256(review)


def _build_attributed_import(store: DirectMemoryStore) -> tuple[str, str, str]:
    imported = store.record_source_event(
        source_id="imported-source",
        project=PROJECT,
        speaker=Speaker.USER,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=0,
    )
    payload_sha256 = source_authorship_payload_sha256(imported.source_id, imported.sha256, "self")
    store.record_live_user_input(
        source_id="live-authorship-attestation",
        project=PROJECT,
        said_at=NOW,
        exact_text="I confirm this synthetic imported statement is mine.",
        authorization_intent=AuthorizationIntent(
            action="source_authorship",
            payload_sha256=payload_sha256,
            subject_id="self",
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        "live-authorship-attestation",
        action="source_authorship",
        payload_sha256=payload_sha256,
        subject_id="self",
    )
    store.attribute_source_authorship(
        imported.source_id,
        authorization,
        expected_revision=store.current_revision(PROJECT),
    )
    native = make_native_review(source_id=imported.source_id)
    stored = store.build_review(
        imported.source_id,
        native.source,
        (
            FactProposal(
                fact_key="communication.concise",
                evidence_ids=(imported.source_id,),
                proposal=native.claims[0],
            ),
        ),
        expected_revision=store.current_revision(PROJECT),
    )

    return stored.source_id, stored.review.source.response_sha256, imported.sha256


def test_imported_user_authorship_requires_and_accepts_bound_live_attestation(
    tmp_path: Path,
) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=SYNTHETIC_PLANE
    )
    source_id, review_source_hash, imported_hash = _build_attributed_import(store)
    assert source_id == "imported-source"
    assert review_source_hash == imported_hash
