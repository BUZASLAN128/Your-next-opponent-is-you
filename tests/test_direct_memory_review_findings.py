from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_TEXT, make_native_review
from ynoy.direct_memory import (
    AuthorizationIntent,
    DirectMemoryStore,
    FactProposal,
    ProvenanceState,
    RevisionKind,
)
from ynoy.direct_memory.codec import claim_revision_payload_sha256, correction_payload_sha256
from ynoy.errors import DataValidationError
from ynoy.models import (
    ClaimModality,
    MarkTemporaryClaimDecision,
    NarrowScopeClaimDecision,
    ScopeRef,
)


def _review(store: DirectMemoryStore, source_id: str):
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=store.current_revision(PROJECT),
    )
    native = make_native_review(source_id=source_id)
    claim = native.claims[0].model_copy(
        update={"modality": ClaimModality.SHOULD, "literal_normalization": "A scoped preference."}
    )
    review = native.model_copy(update={"claims": (claim,)})
    stored = store.build_review(
        source_id,
        review.source,
        (FactProposal(fact_key="policy.scope", evidence_ids=(source_id,), proposal=claim),),
        expected_revision=store.current_revision(PROJECT),
    )
    return review, stored


def _authorized_correction(store, review, stored, source_id: str, decision):
    decisions = (decision,)
    digest = correction_payload_sha256(decisions, operation="correct")
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=f"Authorize correction {source_id}.",
        authorization_intent=AuthorizationIntent(
            action="correct",
            payload_sha256=digest,
            subject_id="self",
            review_sha256=stored.review_sha256,
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        source_id,
        action="correct",
        payload_sha256=digest,
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    return decisions, authorization


def _scope_then_prepare_temporary(store, review, stored, clock):
    claim_id = review.claims[0].record_id
    scoped, scope_auth = _authorized_correction(
        store,
        review,
        stored,
        "scope-sequence-auth",
        NarrowScopeClaimDecision(
            claim_id=claim_id,
            subject_id="self",
            replacement_scope=ScopeRef(person_id="self", project=PROJECT),
        ),
    )
    first = store.apply_correction(
        stored.review_id,
        scoped,
        authorization=scope_auth,
        expected_revision=store.current_revision(PROJECT),
    )
    before_history = store.list_corrections(stored.review_id)
    assert first.state.claims[0].effective_claims[0].scope.project == PROJECT
    persisted = store.list_corrections(stored.review_id)[0]
    assert persisted.state.claims[0].effective_claims[0].scope.project == PROJECT
    clock[0] = NOW + timedelta(days=1)
    temporary, temporary_auth = _authorized_correction(
        store,
        review,
        stored,
        "temporary-after-scope-auth",
        MarkTemporaryClaimDecision(
            claim_id=claim_id,
            subject_id="self",
            valid_until=NOW + timedelta(days=5),
        ),
    )
    return store.current_revision(PROJECT), before_history, temporary, temporary_auth


def test_scope_to_temporary_cannot_drop_existing_scope_and_rolls_back(tmp_path: Path) -> None:
    clock = [NOW]
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: clock[0])
    review, stored = _review(store, "scope-sequence-source")
    before_revision, before_history, temporary, temporary_auth = _scope_then_prepare_temporary(
        store, review, stored, clock
    )
    with pytest.raises(DataValidationError) as unsafe:
        store.apply_correction(
            stored.review_id,
            temporary,
            authorization=temporary_auth,
            expected_revision=before_revision,
        )
    assert unsafe.value.code == "direct_memory_incremental_correction_unsafe"
    assert store.current_revision(PROJECT) == before_revision
    assert store.list_corrections(stored.review_id) == before_history
    retry = store.authorize_action(
        "temporary-after-scope-auth",
        action="correct",
        payload_sha256=temporary_auth.payload_sha256,
        subject_id="self",
        review_sha256=stored.review_sha256,
    )
    assert retry.live_user_source_id == temporary_auth.live_user_source_id


def _failed_tool_authorization(store, result):
    tool = store.record_tool_result(
        source_id="failed-tool-result",
        project=PROJECT,
        tool_name="synthetic-check",
        operation="verify",
        inputs={"item": "synthetic"},
        result=result,
        expected_revision=0,
    )
    payload = {"status": "verified"}
    evidence = (tool.tool_receipt_id,)
    digest = claim_revision_payload_sha256(
        fact_key="workflow.status",
        evidence_ids=evidence,
        state=ProvenanceState.TOOL_VERIFIED,
        kind=RevisionKind.ASSERTION,
        payload=payload,
        event_time=NOW,
        tool_receipt_id=tool.tool_receipt_id,
    )
    store.record_live_user_input(
        source_id="failed-tool-authorization",
        project=PROJECT,
        said_at=NOW,
        exact_text="Authorize synthetic tool-backed claim.",
        authorization_intent=AuthorizationIntent(
            action="claim_revision",
            payload_sha256=digest,
            subject_id="self",
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        "failed-tool-authorization",
        action="claim_revision",
        payload_sha256=digest,
        subject_id="self",
    )
    return tool, payload, evidence, authorization, store.current_revision(PROJECT)


@pytest.mark.parametrize(
    "result",
    (
        {"executed": False},
        {"cancelled": True},
        {"canceled": True},
        {"status": "cancelled"},
        {"status": "canceled"},
        {"status": "failed"},
        {"status": "aborted"},
    ),
)
def test_failed_or_cancelled_tool_receipt_cannot_verify_a_claim(
    tmp_path: Path, result: dict[str, object]
) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    tool, payload, evidence, authorization, before_revision = _failed_tool_authorization(
        store, result
    )

    with pytest.raises(DataValidationError) as contradiction:
        store.append_claim_revision(
            project=PROJECT,
            fact_key="workflow.status",
            evidence_ids=evidence,
            state=ProvenanceState.TOOL_VERIFIED,
            payload=payload,
            authorization=authorization,
            expected_revision=before_revision,
            event_time=NOW,
            tool_receipt_id=tool.tool_receipt_id,
        )
    assert contradiction.value.code == "direct_memory_tool_result_contradiction"
    assert store.current_revision(PROJECT) == before_revision
    assert store.list_claim_revisions(PROJECT) == ()
