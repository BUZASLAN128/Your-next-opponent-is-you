from __future__ import annotations

from pathlib import Path

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT, SOURCE_TEXT
from ynoy.direct_memory import (
    AuthorizationIntent,
    DataPlane,
    DirectMemoryStore,
    ProvenanceState,
    RevisionKind,
)
from ynoy.direct_memory.codec import claim_revision_payload_sha256
from ynoy.errors import DataValidationError


def _authorized_manual_claim(tmp_path: Path, fact_key: str):
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    store.record_live_user_input(
        source_id="key-evidence",
        project=PROJECT,
        said_at=NOW,
        exact_text=SOURCE_TEXT,
        expected_revision=0,
    )
    payload = {"status": "planned"}
    digest = claim_revision_payload_sha256(
        fact_key=fact_key,
        evidence_ids=("key-evidence",),
        state=ProvenanceState.INTENT,
        kind=RevisionKind.ASSERTION,
        payload=payload,
        event_time=NOW,
        tool_receipt_id=None,
    )
    store.record_live_user_input(
        source_id="key-authorization",
        project=PROJECT,
        said_at=NOW,
        exact_text="Authorize this synthetic claim.",
        authorization_intent=AuthorizationIntent(
            action="claim_revision", payload_sha256=digest, subject_id="self"
        ),
        expected_revision=1,
    )
    authorization = store.authorize_action(
        "key-authorization",
        action="claim_revision",
        payload_sha256=digest,
        subject_id="self",
    )
    return store, payload, authorization, digest


@pytest.mark.parametrize("fact_key", [" status ", "x" * 241])
def test_manual_claim_fact_key_is_validated_before_authorization_use(
    tmp_path: Path, fact_key: str
) -> None:
    store, payload, authorization, digest = _authorized_manual_claim(tmp_path, fact_key)
    revision_before = store.current_revision(PROJECT)

    with pytest.raises(DataValidationError) as rejected:
        store.append_claim_revision(
            project=PROJECT,
            fact_key=fact_key,
            evidence_ids=("key-evidence",),
            state=ProvenanceState.INTENT,
            payload=payload,
            authorization=authorization,
            expected_revision=revision_before,
            event_time=NOW,
        )

    assert rejected.value.code == "direct_memory_fact_key_invalid"
    assert store.current_revision(PROJECT) == revision_before
    assert store.authorize_action(
        "key-authorization",
        action="claim_revision",
        payload_sha256=digest,
        subject_id="self",
    ) == authorization


def test_manual_claim_accepts_maximum_canonical_fact_key(tmp_path: Path) -> None:
    fact_key = "x" * 240
    store, payload, authorization, _ = _authorized_manual_claim(tmp_path, fact_key)

    revision = store.append_claim_revision(
        project=PROJECT,
        fact_key=fact_key,
        evidence_ids=("key-evidence",),
        state=ProvenanceState.INTENT,
        payload=payload,
        authorization=authorization,
        expected_revision=2,
        event_time=NOW,
    )

    assert revision.fact_key == fact_key


def test_tool_result_rejects_padded_source_identifier_before_commit(tmp_path: Path) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=DataPlane.PUBLIC_SYNTHETIC
    )

    with pytest.raises(DataValidationError) as rejected:
        store.record_tool_result(
            source_id=" padded-tool-source ",
            project=PROJECT,
            tool_name="fixture-tool",
            operation="verify",
            inputs={"item": "fixture"},
            result={"status": "ok"},
            expected_revision=0,
        )

    assert rejected.value.code == "direct_memory_source_invalid"
    assert store.current_revision(PROJECT) == 0
