from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from conftest import synthetic_audit

from ynoy.corpus.codex import CodexMetadataAdapter
from ynoy.corpus.codex_approval import create_codex_approval
from ynoy.corpus.codex_ingest import ingest_codex_snapshot
from ynoy.corpus.codex_snapshot import snapshot_codex_corpus
from ynoy.corpus.raw_vault import RawVaultStore
from ynoy.errors import DataValidationError
from ynoy.models import (
    CodexIngestionReceipt,
    CodexMetadataInventory,
    CodexSnapshotReceipt,
)
from ynoy.storage import (
    CodexIngestionRepository,
    CorpusVaultRepository,
    Database,
)

pytestmark = pytest.mark.integration

_MARKER = b"YNOY_SYNTHETIC_CODEX_FIXTURE_V1\n"


def _message(index: int) -> dict[str, object]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": f"synthetic-{index}"}],
        },
    }


def _build_snapshot(
    tmp_path: Path,
    database: Database,
    records: tuple[dict[str, object], ...],
) -> tuple[CodexSnapshotReceipt, CodexMetadataInventory, RawVaultStore]:
    source = tmp_path / "source"
    day = source / "sessions" / "2026" / "01" / "01"
    day.mkdir(parents=True)
    (source / ".ynoy-synthetic-codex-fixture").write_bytes(_MARKER)
    name = f"rollout-2026-01-01T00-00-00-{UUID(int=99)}.jsonl"
    (day / name).write_bytes(b"".join(json.dumps(item).encode() + b"\n" for item in records))
    manifest = CodexMetadataAdapter().inventory(source, synthetic=True)
    approval = create_codex_approval(
        manifest,
        allowed_operations=("snapshot", "ingest"),
        retention_days=7,
        third_party_reviewed=False,
    )
    store = RawVaultStore(tmp_path / "private", synthetic=True)
    store.write_approval(approval)
    receipt = snapshot_codex_corpus(source, manifest, approval, store)
    store.write_snapshot(receipt)
    vault = CorpusVaultRepository(database)
    vault.save_approval(approval, synthetic_audit(event_type="approval"), synthetic=True)
    vault.save_snapshot(receipt, synthetic_audit(event_type="snapshot"))
    return receipt, manifest, store


def _resume_and_replay(
    database: Database,
    snapshot: CodexSnapshotReceipt,
    manifest: CodexMetadataInventory,
    store: RawVaultStore,
) -> tuple[CodexIngestionReceipt, CodexIngestionReceipt]:
    resumed = ingest_codex_snapshot(
        snapshot,
        manifest,
        store,
        CodexIngestionRepository(database),
        resume=True,
    )
    replayed = ingest_codex_snapshot(
        snapshot,
        manifest,
        store,
        CodexIngestionRepository(database),
        resume=True,
    )
    return resumed, replayed


def test_ingestion_crash_resume_is_atomic_and_idempotent(
    test_database: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = (
        {"type": "session_meta", "payload": {"id": "synthetic-session"}},
        *(_message(index) for index in range(260)),
    )
    snapshot, manifest, store = _build_snapshot(tmp_path, test_database, records)
    repository = CodexIngestionRepository(test_database)
    real_save = repository.save_batch
    calls = 0

    def fail_second_batch(checkpoint, events, parser_state):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic crash")
        return real_save(checkpoint, events, parser_state)

    monkeypatch.setattr(repository, "save_batch", fail_second_batch)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        ingest_codex_snapshot(snapshot, manifest, store, repository, resume=False)
    summary = CodexIngestionRepository(test_database).summary(snapshot.snapshot_id)
    assert summary["event_count"] == 250
    with pytest.raises(DataValidationError) as blocked:
        ingest_codex_snapshot(
            snapshot,
            manifest,
            store,
            CodexIngestionRepository(test_database),
            resume=False,
        )
    assert blocked.value.code == "codex_ingest_resume_required"

    resumed, replayed = _resume_and_replay(test_database, snapshot, manifest, store)
    assert resumed.status == replayed.status == "complete"
    assert resumed.normalized_event_count == replayed.normalized_event_count == len(records)
    assert resumed.processed_bytes == replayed.processed_bytes == snapshot.expected_bytes


def test_stale_checkpoint_and_disconnected_batch_fail_closed(
    test_database: Database,
    tmp_path: Path,
) -> None:
    records = ({"type": "session_meta", "payload": {"id": "synthetic-session"}}, _message(1))
    snapshot, _, _ = _build_snapshot(tmp_path, test_database, records)
    repository = CodexIngestionRepository(test_database)
    checkpoint = repository.prepare(snapshot.snapshot_id)[0]

    with pytest.raises(DataValidationError) as invalid:
        repository.save_batch(checkpoint, [], {})
    assert invalid.value.code == "codex_ingest_batch_size_invalid"
