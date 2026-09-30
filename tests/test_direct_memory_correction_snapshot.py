from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_ID, SOURCE_TEXT, make_native_review
from ynoy.decision_brief import resolve_decision_brief
from ynoy.direct_memory import AuthorizationIntent, DataPlane, DirectMemoryStore, FactProposal
from ynoy.direct_memory.codec import correction_payload_sha256
from ynoy.errors import DataValidationError
from ynoy.models import ConfirmClaimDecision, ScopeRef
from ynoy.util import canonical_sha256


def _store_with_mutator(tmp_path: Path, supersessions: dict[str, str], trigger: int):
    armed = [False]
    calls = [0]

    def clock():
        if armed[0]:
            calls[0] += 1
            if calls[0] == trigger:
                supersessions["preference.concise"] = "unapproved.replacement"
                armed[0] = False
        return NOW

    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3",
        clock=clock,
        data_plane=DataPlane.PUBLIC_SYNTHETIC,
    )
    return store, armed, calls


def _fixture(tmp_path: Path, supersessions: dict[str, str], trigger: int):
    store, armed, calls = _store_with_mutator(tmp_path, supersessions, trigger)
    stored, source_sha = _persist_review(store)
    decisions = (
        ConfirmClaimDecision(claim_id=stored.review.claims[0].record_id, subject_id="self"),
    )
    authorization, digest = _authorize(store, stored, decisions)
    return store, stored, decisions, authorization, digest, source_sha, armed, calls


def _persist_review(store: DirectMemoryStore):
    native = make_native_review()
    source = store.record_live_user_input(
        source_id=SOURCE_ID,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=0,
    )
    stored = store.build_review(
        SOURCE_ID,
        native.source,
        (
            FactProposal(
                fact_key="preference.concise",
                evidence_ids=(SOURCE_ID,),
                proposal=native.claims[0],
            ),
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    return stored, source.sha256


def _authorize(store: DirectMemoryStore, stored, decisions):
    digest = correction_payload_sha256(decisions, operation="correct", supersessions={})
    auth_source_id = "mutable-correction-authorization"
    store.record_live_user_input(
        source_id=auth_source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text="Explicitly authorize this synthetic correction.",
        authorization_intent=AuthorizationIntent(
            action="correct",
            payload_sha256=digest,
            subject_id="self",
            review_sha256=stored.review_sha256,
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        auth_source_id,
        action="correct",
        payload_sha256=digest,
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    return authorization, digest


def _assert_refused(
    store, stored, authorization, digest, source_sha, revision, previous_claims
) -> None:
    assert store.current_revision(PROJECT) == revision
    assert store.list_corrections(stored.review_id) == ()
    assert store.list_claim_revisions(PROJECT) == previous_claims
    assert store.get_source_event(SOURCE_ID).sha256 == source_sha
    assert store.authorize_action(
        authorization.live_user_source_id,
        action="correct",
        payload_sha256=digest,
        subject_id="self",
        review_sha256=stored.review_sha256,
    )


def _assert_consumed(reloaded, stored, decisions, authorization) -> None:
    with pytest.raises(DataValidationError) as replayed:
        reloaded.apply_correction(
            stored.review_id,
            decisions,
            authorization=authorization,
            expected_revision=reloaded.current_revision(PROJECT),
            operation="correct",
            supersessions={},
        )
    assert replayed.value.code == "direct_memory_authorization_required"


def _assert_persisted_snapshot(
    tmp_path: Path, stored, decisions, authorization, digest, source_sha, applied, as_of
) -> None:
    reloaded = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    history = reloaded.list_corrections(stored.review_id)
    assert len(history) == 1
    assert history[0].supersessions == {}
    assert history[0].authorization.payload_sha256 == digest
    assert history[0].correction.receipt_sha256 == applied.correction.receipt_sha256
    assert history[0].state.state_sha256 == applied.state.state_sha256
    assert reloaded.get_source_event(SOURCE_ID).sha256 == source_sha
    assert reloaded.get_review(stored.review_id).review_sha256 == stored.review_sha256
    brief = reloaded.brief(PROJECT, as_of=as_of, known_at=as_of)
    native = resolve_decision_brief(
        applied.state, ScopeRef(person_id="self", project=PROJECT), as_of
    )
    assert brief.native_briefs == (native,)
    assert brief.native_brief_hashes == (canonical_sha256(native.model_dump(mode="json")),)
    _assert_consumed(reloaded, stored, decisions, authorization)


@pytest.mark.parametrize("clock_trigger", (1, 2))
def test_mutable_supersession_input_cannot_change_authorized_correction_wrapper(
    tmp_path: Path, clock_trigger: int
) -> None:
    supersessions: dict[str, str] = {}
    store, stored, decisions, authorization, digest, source_sha, armed, calls = _fixture(
        tmp_path, supersessions, clock_trigger
    )
    revision = store.current_revision(PROJECT)
    previous_claims = store.list_claim_revisions(PROJECT)
    as_of = NOW + timedelta(days=1)
    armed[0] = True
    try:
        applied = store.apply_correction(
            stored.review_id,
            decisions,
            authorization=authorization,
            expected_revision=revision,
            operation="correct",
            supersessions=supersessions,
        )
    except DataValidationError:
        assert calls[0] == clock_trigger
        assert supersessions == {"preference.concise": "unapproved.replacement"}
        _assert_refused(
            store, stored, authorization, digest, source_sha, revision, previous_claims
        )
        return

    assert calls[0] == clock_trigger
    assert supersessions == {"preference.concise": "unapproved.replacement"}
    assert applied.supersessions == {}
    assert applied.authorization.payload_sha256 == digest
    assert applied.correction.receipt_sha256
    _assert_persisted_snapshot(
        tmp_path, stored, decisions, authorization, digest, source_sha, applied, as_of
    )
