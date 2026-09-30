from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_ID, SOURCE_TEXT, make_native_review
from ynoy.direct_memory import (
    AuthorizationIntent,
    DataPlane,
    DirectMemoryStore,
    FactProposal,
    ProvenanceState,
    RevisionKind,
)
from ynoy.direct_memory.codec import claim_revision_payload_sha256
from ynoy.errors import DataValidationError


def _digest(
    payload: dict[str, Any],
    state: ProvenanceState,
    evidence: tuple[str, ...],
    tool_id: str | None,
) -> str:
    return claim_revision_payload_sha256(
        fact_key="workflow.snapshot",
        evidence_ids=evidence,
        state=state,
        kind=RevisionKind.ASSERTION,
        payload=payload,
        event_time=NOW,
        tool_receipt_id=tool_id,
    )


def _authorization(
    store: DirectMemoryStore,
    digest: str,
    source_id: str,
    *,
    expected_revision: int,
):
    store.record_live_user_input(
        source_id=source_id,
        project=PROJECT,
        said_at=NOW,
        exact_text=f"Authorize snapshot append {source_id}.",
        authorization_intent=AuthorizationIntent(
            action="claim_revision",
            payload_sha256=digest,
            subject_id="self",
        ),
        expected_revision=expected_revision,
    )
    return store.authorize_action(
        source_id,
        action="claim_revision",
        payload_sha256=digest,
        subject_id="self",
    )


def _assert_rollback_and_unused_authorization(
    store: DirectMemoryStore,
    *,
    before_revision: int,
    source_id: str,
    digest: str,
    source_sha256: str,
    native_hashes: tuple[str, ...],
    previous_claims,
):
    assert store.current_revision(PROJECT) == before_revision
    claims = store.list_claim_revisions(PROJECT)
    assert claims == previous_claims
    assert not any(item.fact_key == "workflow.snapshot" for item in claims)
    assert store.get_source_event(SOURCE_ID).sha256 == source_sha256
    assert store.brief(
        PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW
    ).native_brief_hashes == native_hashes
    assert store.authorize_action(
        source_id,
        action="claim_revision",
        payload_sha256=digest,
        subject_id="self",
    )


def _prepare_case(tmp_path: Path, tool_verified: bool):
    store, payload, armed = _base_store(tmp_path)
    native = make_native_review()
    store.build_review(
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
    source_sha256 = store.get_source_event(SOURCE_ID).sha256
    native_hashes = store.brief(
        PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW
    ).native_brief_hashes
    tool_id = None
    evidence = (SOURCE_ID,)
    state = ProvenanceState.INTENT
    if tool_verified:
        result: dict[str, Any] = {"status": "verified", "details": {"step": "A"}}
        tool = store.record_tool_result(
            source_id="snapshot-tool-result",
            project=PROJECT,
            tool_name="synthetic-check",
            operation="verify",
            inputs={"item": "snapshot"},
            result=result,
            expected_revision=store.current_revision(PROJECT),
        )
        payload.clear()
        payload.update({"status": "verified", "details": result["details"]})
        tool_id = tool.tool_receipt_id
        evidence = (tool_id,)
        state = ProvenanceState.TOOL_VERIFIED
    return (
        store,
        payload,
        armed,
        state,
        evidence,
        tool_id,
        deepcopy(payload),
        source_sha256,
        native_hashes,
    )


def _base_store(tmp_path: Path):
    payload: dict[str, Any] = {"status": "planned", "details": {"step": "A"}}
    armed = [False]

    def clock():
        if armed[0]:
            payload["details"]["step"] = "B"
            armed[0] = False
        return NOW

    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=clock, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    store.record_live_user_input(
        source_id=SOURCE_ID,
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=0,
    )
    return store, payload, armed


def _assert_durable_snapshot(
    path: Path,
    appended,
    expected_payload: dict[str, Any],
    state: ProvenanceState,
    digest: str,
    source_sha256: str,
    native_hashes: tuple[str, ...],
    previous_claims,
):
    reloaded = DirectMemoryStore(
        path, clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    durable = reloaded.list_claim_revisions(PROJECT)
    assert appended.payload == expected_payload
    assert appended.authorization is not None
    assert appended.authorization.payload_sha256 == digest
    assert durable[:-1] == previous_claims
    assert len(durable) == len(previous_claims) + 1
    assert durable[-1].fact_key == "workflow.snapshot"
    assert durable[-1].state == state
    assert durable[-1].payload == expected_payload
    assert durable[-1].authorization is not None
    assert durable[-1].authorization.payload_sha256 == digest
    assert (
        _digest(
            durable[-1].payload,
            state,
            durable[-1].evidence_ids,
            durable[-1].tool_receipt_id,
        )
        == digest
    )
    assert reloaded.get_source_event(SOURCE_ID).sha256 == source_sha256
    assert reloaded.brief(
        PROJECT, as_of=NOW + timedelta(days=1), known_at=NOW
    ).native_brief_hashes == native_hashes


def _authorized_append(store, payload, state, evidence, tool_id):
    digest = _digest(payload, state, evidence, tool_id)
    source_id = "snapshot-live-authorization"
    authorization = _authorization(
        store,
        digest,
        source_id,
        expected_revision=store.current_revision(PROJECT),
    )
    return digest, source_id, authorization, store.current_revision(PROJECT)


def _attempt_append(store, payload, state, evidence, tool_id, authorization, revision):
    try:
        return store.append_claim_revision(
            project=PROJECT,
            fact_key="workflow.snapshot",
            evidence_ids=evidence,
            state=state,
            payload=payload,
            authorization=authorization,
            expected_revision=revision,
            event_time=NOW,
            tool_receipt_id=tool_id,
        )
    except DataValidationError:
        return None


@pytest.mark.parametrize("tool_verified", (False, True))
def test_append_snapshots_payload_before_authorized_sqlite_write(
    tmp_path: Path, tool_verified: bool
) -> None:
    (
        store,
        payload,
        armed,
        state,
        evidence,
        tool_id,
        expected_payload,
        source_sha256,
        native_hashes,
    ) = _prepare_case(tmp_path, tool_verified)
    digest, auth_source_id, authorization, before_revision = _authorized_append(
        store, payload, state, evidence, tool_id
    )
    previous_claims = store.list_claim_revisions(PROJECT)
    armed[0] = True
    appended = _attempt_append(
        store, payload, state, evidence, tool_id, authorization, before_revision
    )
    assert payload["details"]["step"] == "B"
    if appended is None:
        _assert_rollback_and_unused_authorization(
            store,
            before_revision=before_revision,
            source_id=auth_source_id,
            digest=digest,
            source_sha256=source_sha256,
            native_hashes=native_hashes,
            previous_claims=previous_claims,
        )
        return

    _assert_durable_snapshot(
        tmp_path / "memory.sqlite3",
        appended,
        expected_payload,
        state,
        digest,
        source_sha256,
        native_hashes,
        previous_claims,
    )
