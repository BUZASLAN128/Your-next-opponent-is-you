from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT
from tests.test_direct_memory_correction_snapshot import _fixture
from ynoy.direct_memory import ClaimRevision, DirectMemoryStore, ProvenanceState, RevisionKind
from ynoy.direct_memory.codec import claim_revision_payload_sha256
from ynoy.errors import DataValidationError


def _rewrite_revision_metadata(
    store: DirectMemoryStore, revision: ClaimRevision, changes: dict[str, object]
) -> None:
    changed, digest = _changed_metadata_payload(revision, changes)
    connection = sqlite3.connect(store.database.path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DROP TRIGGER immutable_claim_revisions_update")
        connection.execute(
            "UPDATE claim_revisions SET state=?,kind=?,related_fact_key=?,tool_receipt_id=? "
            "WHERE revision_id=?",
            (
                changed["state"].value,
                changed["kind"].value,
                changed["related_fact_key"],
                changed["tool_receipt_id"],
                revision.revision_id,
            ),
        )
        connection.execute(
            "UPDATE claim_revisions SET event_time=?,recorded_at=?,revision=?,payload_sha256=? "
            "WHERE revision_id=?",
            (
                changed["event_time"].isoformat() if changed["event_time"] else None,
                changed["recorded_at"].isoformat(),
                changed["revision"],
                digest,
                revision.revision_id,
            ),
        )
        connection.execute(
            "CREATE TRIGGER immutable_claim_revisions_update BEFORE UPDATE ON claim_revisions "
            "BEGIN SELECT RAISE(ABORT, 'append-only direct-memory record'); END"
        )
        connection.commit()
    finally:
        connection.close()


def _changed_metadata_payload(
    revision: ClaimRevision, changes: dict[str, object]
) -> tuple[dict[str, object], str]:
    changed = {
        "state": revision.state,
        "kind": revision.kind,
        "related_fact_key": revision.related_fact_key,
        "tool_receipt_id": revision.tool_receipt_id,
        "event_time": revision.event_time,
        "recorded_at": revision.recorded_at,
        "revision": revision.revision,
    }
    changed.update(changes)
    digest = claim_revision_payload_sha256(
        fact_key=revision.fact_key,
        evidence_ids=revision.evidence_ids,
        state=changed["state"],
        kind=changed["kind"],
        payload=revision.payload,
        event_time=changed["event_time"],
        tool_receipt_id=changed["tool_receipt_id"],
        related_fact_key=changed["related_fact_key"],
    )
    return changed, digest


def _store_with_tampered_correction_revision(
    tmp_path: Path, changes: dict[str, object]
) -> DirectMemoryStore:
    store, stored, decisions, authorization, _, _, _, _ = _fixture(tmp_path, {}, trigger=99)
    tool = store.record_tool_result(
        source_id="metadata-tamper-tool",
        project=PROJECT,
        tool_name="fixture-tool",
        operation="verify",
        inputs={"item": "fixture"},
        result={"status": "ok"},
        expected_revision=store.current_revision(PROJECT),
    )
    if changes.get("tool_receipt_id") is not None:
        assert tool.tool_receipt_id == changes["tool_receipt_id"]
    store.apply_correction(
        stored.review_id,
        decisions,
        authorization=authorization,
        expected_revision=store.current_revision(PROJECT),
        operation="correct",
        supersessions={},
    )
    revision = store.list_claim_revisions(PROJECT)[-1]
    _rewrite_revision_metadata(store, revision, changes)
    return store


@pytest.mark.parametrize(
    "changes",
    [
        {"state": ProvenanceState.REJECTED},
        {"kind": RevisionKind.RETRACTION},
        {"kind": RevisionKind.SUPERSESSION, "related_fact_key": "replacement"},
        {"tool_receipt_id": "metadata-tamper-tool"},
        {"event_time": NOW + timedelta(days=2)},
        {"recorded_at": NOW + timedelta(days=2)},
        {"revision": 100},
    ],
    ids=["state", "kind", "related-fact", "tool-receipt", "event-time", "recorded-at", "revision"],
)
def test_self_consistent_correction_revision_metadata_tampering_is_rejected(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    store = _store_with_tampered_correction_revision(tmp_path, changes)

    with pytest.raises(DataValidationError) as rejected:
        store.list_claim_revisions(PROJECT)
    assert rejected.value.code == "direct_memory_claim_revision_integrity"


@pytest.mark.parametrize("surface", ["list", "brief", "export"])
def test_cutoff_surfaces_reject_correction_outcome_revision_outside_watermark(
    tmp_path: Path, surface: str
) -> None:
    store = _store_with_tampered_correction_revision(tmp_path, {"revision": 100})
    cutoff = NOW + timedelta(days=2)

    with pytest.raises(DataValidationError) as rejected:
        if surface == "list":
            store.list_claim_revisions(PROJECT)
        elif surface == "brief":
            store.brief(PROJECT, as_of=cutoff, known_at=cutoff)
        else:
            store.export_jsonl(PROJECT)
    assert rejected.value.code == "direct_memory_claim_revision_integrity"
