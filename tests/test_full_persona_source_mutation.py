from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.full_persona import prepared_full_persona_source

from ynoy.errors import DataValidationError
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import FullCorpusFileReceipt, FullCorpusLimits


def _frozen_run(tmp_path: Path):
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)
    return source_root, private_root, manifest


def _source_path(source_root: Path, manifest, index: int = 0) -> Path:
    source = manifest.files[index]
    return source_root / source.partition / Path(source.relative_locator)


def _mutate_same_metadata(path: Path) -> None:
    original = path.read_bytes()
    marker = b"PRIVATE_CONTEXT_00"
    offset = original.index(marker)
    changed = bytearray(original)
    changed[offset + len(marker) - 1] ^= 1
    mtime_ns = path.stat().st_mtime_ns
    path.write_bytes(changed)
    os.utime(path, ns=(mtime_ns, mtime_ns))
    assert path.stat().st_size == len(original)
    assert path.stat().st_mtime_ns == mtime_ns


def _assert_source_mutation(error: pytest.ExceptionInfo[DataValidationError]) -> None:
    assert error.value.code in {
        "full_persona_source_changed",
        "full_persona_source_universe_changed",
    }


def _add_large_evidence_file(source_root: Path, *, size: int) -> Path:
    path = (
        source_root
        / "sessions"
        / "2025"
        / "12"
        / "31"
        / "rollout-2025-12-31T04-04-05-ffffffff-ffff-ffff-ffff-ffffffffffff.jsonl"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with path.open("wb") as stream:
        metadata = {"type": "session_meta", "payload": {"id": "large-session"}}
        encoded = (json.dumps(metadata, separators=(",", ":")) + "\n").encode()
        stream.write(encoded)
        total += len(encoded)
        index = 0
        while total < size:
            record = {
                "type": "response_item",
                "timestamp": f"2025-12-31T04:{index % 60:02d}:00+00:00",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": f"large evidence {index}"}],
                },
            }
            encoded = (json.dumps(record, separators=(",", ":")) + "\n").encode()
            stream.write(encoded)
            total += len(encoded)
            index += 1
    stable_ns = int(datetime(2025, 12, 31, 4, 4, 5, tzinfo=UTC).timestamp() * 1_000_000_000)
    os.utime(path, ns=(stable_ns, stable_ns))
    return path


def _resume_with_budget(source_root: Path, private_root: Path, run_id: str):
    heads = []
    head = scan_full_corpus(
        source_root,
        private_root,
        run_id,
        synthetic=True,
        max_input_bytes=512 * 1024,
    )
    heads.append(head)
    while head.status != "complete":
        previous = head
        head = scan_full_corpus(
            source_root,
            private_root,
            run_id,
            synthetic=True,
            max_input_bytes=512 * 1024,
        )
        heads.append(head)
        assert head.revision > previous.revision
        assert head.processed_input_bytes - previous.processed_input_bytes <= 512 * 1024
        assert len(head.parser_state) <= 8
        assert len(head.context) <= 4
    return head, tuple(heads)


def test_completed_scan_rechecks_source_digests_on_next_status_call(tmp_path: Path) -> None:
    source_root, private_root, manifest = _frozen_run(tmp_path)
    complete = scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    assert complete.status == "complete"

    _mutate_same_metadata(_source_path(source_root, manifest))

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    _assert_source_mutation(error)
    assert FullPersonaStore(private_root, synthetic=True).read_head(manifest.run_id) == complete


def test_resume_rejects_completed_file_mutation_before_new_evidence_commit(
    tmp_path: Path,
) -> None:
    source_root, private_root, manifest = _frozen_run(tmp_path)
    first_file = manifest.files[0]
    partial = scan_full_corpus(
        source_root,
        private_root,
        manifest.run_id,
        synthetic=True,
        max_input_bytes=first_file.file_bytes,
    )
    assert partial.status == "scanning"
    assert partial.file_index == 1
    assert partial.next_byte_offset == 0

    _mutate_same_metadata(_source_path(source_root, manifest))
    store = FullPersonaStore(private_root, synthetic=True)
    shards_before = tuple(store.iter_shard_paths(manifest.run_id))

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    _assert_source_mutation(error)
    assert store.read_head(manifest.run_id) == partial
    assert tuple(store.iter_shard_paths(manifest.run_id)) == shards_before


def test_large_canonical_file_reconciles_across_bounded_resume_checkpoints(
    tmp_path: Path,
) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    large = _add_large_evidence_file(source_root, size=4 * 1024**2 + 257)
    limits = FullCorpusLimits(
        source_chunk_bytes=64 * 1024,
        max_checkpoint_input_bytes=256 * 1024,
    )
    manifest = freeze_full_corpus(
        source_root,
        private_root,
        prepared.manifest.study_id,
        synthetic=True,
        limits=limits,
    )
    store = FullPersonaStore(private_root, synthetic=True)
    store.write_manifest(manifest)
    large_locator = large.relative_to(source_root / "sessions").as_posix()
    large_source = next(item for item in manifest.files if item.relative_locator == large_locator)
    assert large_source.file_bytes > 4 * 1024**2

    head, heads = _resume_with_budget(source_root, private_root, manifest.run_id)

    assert head.file_index == manifest.expected_file_count
    assert head.processed_input_bytes == manifest.expected_input_bytes
    assert head.processed_record_count > 0
    assert head.evidence_count > 0
    receipts = tuple(
        FullCorpusFileReceipt.model_validate_json(
            (store.run_path(manifest.run_id) / "files" / f"{index:08d}.json").read_bytes()
        )
        for index in range(head.file_index)
    )
    large_receipt = next(item for item in receipts if item.source_key == large_source.source_key)
    assert large_receipt.processed_bytes == large.stat().st_size
    assert large_receipt.evidence_count > 0
    assert sum(item.processed_bytes for item in receipts) == head.processed_input_bytes
    assert sum(item.record_count for item in receipts) == head.processed_record_count
    assert sum(item.evidence_count for item in receipts) == head.evidence_count
    assert len(heads) > 1
