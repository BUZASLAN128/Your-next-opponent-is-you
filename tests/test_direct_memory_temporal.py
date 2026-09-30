from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_ID
from ynoy.direct_memory import (
    AuthorizationIntent,
    ClaimRevision,
    DirectMemoryStore,
    ProvenanceState,
    RevisionKind,
)
from ynoy.direct_memory.codec import claim_revision_payload_sha256
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.errors import DataValidationError
from ynoy.models import Speaker


def test_claim_history_preserves_x_y_x_without_treating_intent_as_done(
    tmp_path: Path,
) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    store.record_live_user_input(
        source_id=SOURCE_ID,
        project=PROJECT,
        said_at=NOW,
        exact_text="Synthetic status evidence.",
        expected_revision=0,
    )
    states = (
        (ProvenanceState.INTENT, {"status": "planned"}),
        (ProvenanceState.REPORTED_DONE, {"status": "reported"}),
        (ProvenanceState.INTENT, {"status": "planned"}),
    )
    for index, (state, payload) in enumerate(states):
        _append_authorized_revision(store, index, state, payload)

    brief = store.brief(PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW + timedelta(days=1))
    history = tuple(item for item in brief.claim_revisions if item.fact_key == "workflow.status")
    assert tuple(item.state for item in history) == tuple(item[0] for item in states)
    assert tuple(item.payload for item in history) == tuple(item[1] for item in states)
    assert history[0].revision < history[1].revision < history[2].revision


def test_event_time_and_recorded_knowledge_cutoffs_are_independent(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: clock[0], data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    store.record_live_user_input(
        source_id="early-source",
        project=PROJECT,
        said_at=NOW - timedelta(days=10),
        exact_text="Earlier source event.",
        expected_revision=0,
    )
    clock[0] = NOW + timedelta(days=2)
    store.record_source_event(
        source_id="late-backfill",
        project=PROJECT,
        speaker=Speaker.USER,
        said_at=NOW - timedelta(days=20),
        exact_text="Late recorded backfill.",
        expected_revision=store.current_revision(PROJECT),
    )
    store.record_source_event(
        source_id="unknown-event-time",
        project=PROJECT,
        speaker=Speaker.USER,
        said_at=None,
        exact_text="Event time was not supplied.",
        expected_revision=store.current_revision(PROJECT),
    )

    historical = store.brief(
        PROJECT,
        as_of=NOW - timedelta(days=15),
        known_at=NOW + timedelta(days=1),
    )
    later_knowledge = store.brief(
        PROJECT,
        as_of=NOW - timedelta(days=15),
        known_at=NOW + timedelta(days=3),
    )
    assert historical.source_events == ()
    assert tuple(item.source_id for item in later_knowledge.source_events) == (
        "late-backfill",
        "unknown-event-time",
    )


def _append_authorized_revision(
    store: DirectMemoryStore,
    index: int,
    state: ProvenanceState,
    payload: dict[str, object],
    *,
    evidence_ids: tuple[str, ...] = (SOURCE_ID,),
    tool_receipt_id: str | None = None,
) -> ClaimRevision:
    digest = claim_revision_payload_sha256(
        fact_key="workflow.status",
        evidence_ids=evidence_ids,
        state=state,
        kind=RevisionKind.ASSERTION,
        payload=payload,
        event_time=NOW,
        tool_receipt_id=tool_receipt_id,
    )
    source_id = f"claim-intent-{index}"
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=f"Authorize claim revision {index}.",
        authorization_intent=AuthorizationIntent(
            action="claim_revision",
            payload_sha256=digest,
            subject_id="self",
        ),
        expected_revision=store.current_revision(PROJECT),
    )
    authorization = store.authorize_action(
        source_id,
        action="claim_revision",
        payload_sha256=digest,
        subject_id="self",
    )
    return store.append_claim_revision(
        project=PROJECT,
        fact_key="workflow.status",
        evidence_ids=evidence_ids,
        state=state,
        payload=payload,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
        event_time=NOW,
        tool_receipt_id=tool_receipt_id,
    )


def test_tool_verified_claim_requires_a_persisted_matching_tool_source(
    tmp_path: Path,
) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    store.record_live_user_input(
        source_id=SOURCE_ID,
        project=PROJECT,
        said_at=NOW,
        exact_text="Authorize checking a synthetic result.",
        expected_revision=0,
    )
    with pytest.raises(DataValidationError) as missing:
        _append_authorized_revision(store, 1, ProvenanceState.TOOL_VERIFIED, {"status": "verified"})
    assert missing.value.code == "direct_memory_tool_evidence_required"

    tool = store.record_tool_result(
        source_id="synthetic-tool-result",
        project=PROJECT,
        tool_name="synthetic-check",
        operation="verify",
        inputs={"item": "fixture"},
        result={"status": "verified"},
        expected_revision=store.current_revision(PROJECT),
    )
    revision = _append_authorized_revision(
        store,
        2,
        ProvenanceState.TOOL_VERIFIED,
        {"status": "verified"},
        evidence_ids=(tool.tool_receipt_id,),
        tool_receipt_id=tool.tool_receipt_id,
    )
    assert revision.state == ProvenanceState.TOOL_VERIFIED
    assert revision.tool_receipt_id == tool.tool_receipt_id
