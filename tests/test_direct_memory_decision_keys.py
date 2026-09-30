from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_TEXT, make_native_review
from ynoy.direct_memory import AuthorizationIntent, DirectMemoryStore, FactProposal
from ynoy.direct_memory.codec import correction_payload_sha256
from ynoy.interaction_review import build_interaction_review
from ynoy.models import ClaimModality, ConfirmClaimDecision, TargetLayer


def _persist_review(
    store: DirectMemoryStore,
    source_id: str,
    record_id: int,
    fact_key: str,
    statement: str,
    modality: ClaimModality,
    target_layer: TargetLayer = TargetLayer.PERSONA_CANDIDATE,
):
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=store.current_revision(PROJECT),
    )
    base = make_native_review(source_id=source_id)
    receipt = base.source.model_copy(update={"record_id": UUID(int=record_id)})
    claim = base.claims[0].model_copy(
        update={
            "record_id": UUID(int=record_id + 1),
            "receipt_id": receipt.record_id,
            "literal_normalization": statement,
            "modality": modality,
            "target_layer": target_layer,
        }
    )
    review = build_interaction_review(receipt, (claim,))
    stored = store.build_review(
        source_id,
        review.source,
        (FactProposal(fact_key=fact_key, evidence_ids=(source_id,), proposal=claim),),
        expected_revision=store.current_revision(PROJECT),
    )
    return review, stored


def _confirm(store: DirectMemoryStore, review, stored, source_id: str) -> None:
    decisions = (ConfirmClaimDecision(claim_id=review.claims[0].record_id, subject_id="self"),)
    digest = correction_payload_sha256(decisions, operation="correct")
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=f"Confirm synthetic decision {source_id}.",
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
        stored.review_id,
        decisions,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
    )


@pytest.mark.parametrize(
    ("same_key", "same_statement", "conflicts"),
    ((False, True, False), (True, True, True), (True, False, True)),
)
def test_cross_review_conflict_grouping_uses_reviewed_fact_key(
    tmp_path: Path, same_key: bool, same_statement: bool, conflicts: bool
) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    positive, positive_row = _persist_review(
        store,
        "key-positive-source",
        9100,
        "preference.conciseness",
        "The user prefers concise answers.",
        ClaimModality.SHOULD,
    )
    negative_statement = (
        "The user prefers concise answers."
        if same_statement
        else "The user prefers detailed answers."
    )
    negative, negative_row = _persist_review(
        store,
        "key-negative-source",
        9200,
        "preference.conciseness" if same_key else "preference.detail",
        negative_statement,
        ClaimModality.MUST_NOT,
    )
    _confirm(store, positive, positive_row, "key-positive-confirmation")
    _confirm(store, negative, negative_row, "key-negative-confirmation")

    brief = store.brief(PROJECT, as_of=NOW, known_at=NOW)
    assert len(brief.native_briefs) == 2
    assert all(item.all_entries() for item in brief.native_briefs)
    assert bool(brief.unresolved_conflicts) is conflicts
    assert brief.abstained is conflicts
    assert ("unresolved_conflict" in brief.abstention_reasons) is conflicts
    assert brief.authority == "none" and not brief.automatic_core_promotion


def test_same_fact_key_on_different_layers_does_not_conflict(tmp_path: Path) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    positive, positive_row = _persist_review(
        store,
        "layer-positive-source",
        9700,
        "decision.response_style",
        "The user prefers concise answers.",
        ClaimModality.SHOULD,
        TargetLayer.PERSONA_CANDIDATE,
    )
    negative, negative_row = _persist_review(
        store,
        "layer-negative-source",
        9800,
        "decision.response_style",
        "The user prefers concise answers.",
        ClaimModality.MUST_NOT,
        TargetLayer.SCOPED_POLICY,
    )
    _confirm(store, positive, positive_row, "layer-positive-confirmation")
    _confirm(store, negative, negative_row, "layer-negative-confirmation")

    brief = store.brief(PROJECT, as_of=NOW, known_at=NOW)
    assert len(brief.native_briefs) == 2
    assert all(item.all_entries() for item in brief.native_briefs)
    assert brief.unresolved_conflicts == ()
    assert not brief.abstained
