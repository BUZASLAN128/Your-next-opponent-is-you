from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_TEXT, make_native_review
from tests.test_direct_memory_correction_snapshot import _authorize, _persist_review
from ynoy.direct_memory import (
    AuthorizationIntent,
    DataPlane,
    DirectMemoryStore,
    FactProposal,
    ProvenanceState,
)
from ynoy.direct_memory.claims import ClaimOperations
from ynoy.direct_memory.codec import correction_payload_sha256
from ynoy.direct_memory.exporting import ExportOperations
from ynoy.models import ClaimModality, ConfirmClaimDecision


def _confirm(store: DirectMemoryStore, review_id: str) -> None:
    stored = store.get_review(review_id)
    decision = ConfirmClaimDecision(claim_id=stored.review.claims[0].record_id, subject_id="self")
    digest = correction_payload_sha256((decision,), operation="correct", supersessions={})
    source_id = f"auth-{review_id}"
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text="Authorize this synthetic correction.",
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
    store.apply_correction(
        review_id,
        (decision,),
        authorization,
        expected_revision=store.current_revision(PROJECT),
        operation="correct",
        supersessions={},
    )


def _apply_confirmation(store: DirectMemoryStore, stored, authorization) -> None:
    decision = ConfirmClaimDecision(
        claim_id=stored.review.claims[0].record_id, subject_id="self"
    )
    store.apply_correction(
        stored.review_id,
        (decision,),
        authorization,
        expected_revision=store.current_revision(PROJECT),
        operation="correct",
        supersessions={},
    )


def _inject_brief_correction_after_claim_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    store: DirectMemoryStore,
    stored,
    authorization,
) -> list[bool]:
    original = ClaimOperations.list_claim_revisions
    injected = [False]

    def revise_after_claim_snapshot(
        operations,
        project,
        *,
        known_at=None,
        as_of=None,
        revision_cutoff=None,
    ):
        cutoff_options = (
            {"revision_cutoff": revision_cutoff} if revision_cutoff is not None else {}
        )
        revisions = original(
            operations, project, known_at=known_at, as_of=as_of, **cutoff_options
        )
        if not injected[0]:
            injected[0] = True
            _apply_confirmation(store, stored, authorization)
        return revisions

    monkeypatch.setattr(ClaimOperations, "list_claim_revisions", revise_after_claim_snapshot)
    return injected


def _inject_export_correction_before_reviews(
    monkeypatch: pytest.MonkeyPatch,
    store: DirectMemoryStore,
    stored,
    authorization,
) -> list[bool]:
    original = ExportOperations._export_reviews
    injected = [False]

    def revise_before_reviews(
        operations, project, entries, *, revision_cutoff=None
    ) -> None:
        if not injected[0]:
            injected[0] = True
            _apply_confirmation(store, stored, authorization)
        cutoff_options = (
            {"revision_cutoff": revision_cutoff} if revision_cutoff is not None else {}
        )
        original(operations, project, entries, **cutoff_options)

    monkeypatch.setattr(ExportOperations, "_export_reviews", revise_before_reviews)
    return injected


def test_brief_uses_one_project_revision_snapshot_for_claims_and_corrections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    stored, _ = _persist_review(store)
    authorization, _ = _authorize(
        store,
        stored,
        (ConfirmClaimDecision(claim_id=stored.review.claims[0].record_id, subject_id="self"),),
    )
    injected = _inject_brief_correction_after_claim_snapshot(
        monkeypatch, store, stored, authorization
    )

    brief = store.brief(PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW + timedelta(days=1))

    assert injected[0]
    assert [item.state for item in brief.claim_revisions] == [ProvenanceState.PROPOSED]
    assert brief.native_briefs and not any(item.all_entries() for item in brief.native_briefs)
    assert len(store.list_corrections(stored.review_id)) == 1


def test_export_uses_one_project_revision_snapshot_for_reviews_and_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    stored, _ = _persist_review(store)
    authorization, _ = _authorize(
        store,
        stored,
        (ConfirmClaimDecision(claim_id=stored.review.claims[0].record_id, subject_id="self"),),
    )
    injected = _inject_export_correction_before_reviews(
        monkeypatch, store, stored, authorization
    )

    first_export = [json.loads(line) for line in store.export_jsonl(PROJECT).splitlines()]
    second_export = [json.loads(line) for line in store.export_jsonl(PROJECT).splitlines()]

    assert injected[0]
    assert not any(item["record_type"] == "correction" for item in first_export)
    first_claims = [
        item["record"] for item in first_export if item["record_type"] == "claim_revision"
    ]
    assert [item["state"] for item in first_claims] == ["proposed"]
    assert any(item["record_type"] == "correction" for item in second_export)
    second_claims = [
        item["record"] for item in second_export if item["record_type"] == "claim_revision"
    ]
    assert [item["state"] for item in second_claims] == ["proposed", "accepted"]


def test_reused_claim_ids_keep_fact_keys_scoped_to_their_reviews(tmp_path: Path) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    review_ids = []
    for index, (source_id, fact_key, modality) in enumerate(
        (
            ("conflict-positive", "preference.concise", ClaimModality.MUST),
            ("conflict-negative", "avoid.preference.concise", ClaimModality.MUST_NOT),
        )
    ):
        source = store.record_live_user_input(
            source_id=source_id,
            project=PROJECT,
            said_at=NOW,
            exact_text=SOURCE_TEXT,
            expected_revision=store.current_revision(PROJECT),
        )
        native = make_native_review(source_id=source_id)
        receipt = native.source.model_copy(update={"record_id": UUID(int=8300 + index)})
        proposal = native.claims[0].model_copy(
            update={"receipt_id": receipt.record_id, "modality": modality}
        )
        stored = store.build_review(
            source_id,
            receipt,
            (FactProposal(fact_key=fact_key, evidence_ids=(source.source_id,), proposal=proposal),),
            expected_revision=store.current_revision(PROJECT),
        )
        review_ids.append(stored.review_id)
        _confirm(store, stored.review_id)

    brief = store.brief(PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW + timedelta(days=1))

    assert len(review_ids) == 2
    assert not brief.unresolved_conflicts
    assert "unresolved_conflict" not in brief.abstention_reasons
    assert sum(len(item.all_entries()) for item in brief.native_briefs) == 2
