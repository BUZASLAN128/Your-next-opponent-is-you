from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.corpus.codex import CodexMetadataAdapter
from ynoy.corpus.codex_approval import create_codex_approval
from ynoy.corpus.codex_snapshot import snapshot_codex_corpus
from ynoy.corpus.raw_vault import RawVaultStore
from ynoy.errors import DataValidationError

_MARKER = b"YNOY_SYNTHETIC_CODEX_FIXTURE_V1\n"
_PRIVATE_TEXT = "SYNTHETIC_PRIVATE_DIALOGUE_MUST_STAY_IN_BLOB"


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "codex"
    (root / "sessions").mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(_MARKER)
    return root


def _path(root: Path, *, day: int, identity: int) -> Path:
    name = f"rollout-2026-01-{day:02d}T03-04-05-{UUID(int=identity)}.jsonl"
    return root / "sessions" / "2026" / "01" / f"{day:02d}" / name


def _content(marker: str = _PRIVATE_TEXT) -> bytes:
    records = (
        {"type": "session_meta", "payload": {"id": "synthetic-session"}},
        {"type": "response_item", "payload": {"type": "message", "content": marker}},
    )
    return b"".join(json.dumps(item).encode() + b"\n" for item in records)


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _approved_snapshot_inputs(root: Path):
    manifest = CodexMetadataAdapter().inventory(root, synthetic=True)
    approval = create_codex_approval(
        manifest,
        allowed_operations=("snapshot", "ingest"),
        retention_days=7,
        third_party_reviewed=False,
    )
    return manifest, approval


def test_snapshot_copies_exact_bytes_and_receipt_contains_no_content(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _path(root, day=1, identity=1)
    content = _content()
    _write(source, content)
    manifest, approval = _approved_snapshot_inputs(root)
    store = RawVaultStore(tmp_path / "private", synthetic=True)

    receipt = snapshot_codex_corpus(root, manifest, approval, store)
    store.write_snapshot(receipt)
    item = receipt.files[0]

    assert receipt.status == "complete"
    assert receipt.expected_bytes == receipt.vaulted_bytes == len(content)
    assert receipt.byte_reconciliation_percent == 100
    assert item.blob_sha256 is not None
    assert store.blob_path(item.blob_sha256).read_bytes() == content
    assert _PRIVATE_TEXT not in receipt.model_dump_json()
    assert source.name not in receipt.model_dump_json()
    assert store.read_snapshot(receipt.snapshot_id) == receipt


def test_identical_files_share_one_content_addressed_blob(tmp_path: Path) -> None:
    root = _root(tmp_path)
    content = _content()
    _write(_path(root, day=1, identity=1), content)
    _write(_path(root, day=2, identity=2), content)
    manifest, approval = _approved_snapshot_inputs(root)
    store = RawVaultStore(tmp_path / "private", synthetic=True)

    receipt = snapshot_codex_corpus(root, manifest, approval, store)
    hashes = {item.blob_sha256 for item in receipt.files}

    assert len(hashes) == 1
    assert len(list((store.vault / "blobs").rglob("?" * 64))) == 1
    assert receipt.vaulted_file_count == 2
    assert receipt.vaulted_bytes == len(content) * 2


def test_bounded_canary_resumes_same_snapshot_to_full_reconciliation(tmp_path: Path) -> None:
    root = _root(tmp_path)
    first = _content("first synthetic dialogue")
    second = _content("second synthetic dialogue")
    _write(_path(root, day=1, identity=1), first)
    _write(_path(root, day=2, identity=2), second)
    manifest, approval = _approved_snapshot_inputs(root)
    store = RawVaultStore(tmp_path / "private", synthetic=True)

    canary = snapshot_codex_corpus(root, manifest, approval, store, max_new_bytes=len(first))
    resumed = snapshot_codex_corpus(root, manifest, approval, store, previous=canary)

    assert canary.status == "partial"
    assert {item.status for item in canary.files} == {"vaulted", "deferred_rollout"}
    assert resumed.status == "complete"
    assert resumed.snapshot_id == canary.snapshot_id
    assert resumed.previous_receipt_sha256 == canary.receipt_sha256
    assert resumed.expected_bytes == resumed.vaulted_bytes == len(first) + len(second)


def test_changed_source_is_deferred_instead_of_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    _write(_path(root, day=1, identity=1), _content())
    manifest, approval = _approved_snapshot_inputs(root)
    store = RawVaultStore(tmp_path / "private", synthetic=True)

    def unstable(*_: object) -> tuple[str, int]:
        raise DataValidationError(
            "codex_source_changed_during_snapshot", "synthetic source changed"
        )

    monkeypatch.setattr(store, "vault_file", unstable)
    receipt = snapshot_codex_corpus(root, manifest, approval, store)

    assert receipt.status == "partial"
    assert receipt.files[0].status == "deferred_unstable"
    assert receipt.vaulted_bytes == 0
    assert receipt.expected_bytes == manifest.total_bytes


def test_unapproved_new_file_and_corrupted_blob_fail_closed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write(_path(root, day=1, identity=1), _content())
    manifest, approval = _approved_snapshot_inputs(root)
    store = RawVaultStore(tmp_path / "private", synthetic=True)
    receipt = snapshot_codex_corpus(root, manifest, approval, store)
    item = receipt.files[0]
    assert item.blob_sha256 is not None

    store.blob_path(item.blob_sha256).write_bytes(b"corrupt")
    with pytest.raises(DataValidationError) as corrupt:
        snapshot_codex_corpus(root, manifest, approval, store, previous=receipt)
    assert corrupt.value.code == "raw_vault_blob_size_mismatch"

    _write(_path(root, day=2, identity=2), _content("unapproved"))
    with pytest.raises(DataValidationError) as unapproved:
        snapshot_codex_corpus(root, manifest, approval, store)
    assert unapproved.value.code == "codex_snapshot_unapproved_source"
