from __future__ import annotations

from pathlib import Path

import pytest
from support.full_persona import prepared_full_persona_source

from ynoy.errors import DataValidationError
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore


def _frozen_run(tmp_path: Path):
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)
    return source_root, private_root, manifest


def test_scan_persists_bounded_cursor_and_resumes_to_reconciled_completion(
    tmp_path: Path,
) -> None:
    source_root, private_root, manifest = _frozen_run(tmp_path)

    partial = scan_full_corpus(
        source_root,
        private_root,
        manifest.run_id,
        synthetic=True,
        max_input_bytes=1024,
    )
    assert partial.status == "scanning"
    assert partial.next_byte_offset > 0
    assert partial.processed_input_bytes <= 1024
    assert partial.shard_count >= 1

    complete = scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    assert complete.status == "complete"
    assert complete.processed_input_bytes == manifest.expected_input_bytes
    assert complete.file_index == manifest.expected_file_count
    assert complete.shard_count >= partial.shard_count
    assert complete.head_sha256 != partial.head_sha256


def test_scan_rejects_non_anchor_source_mutation_after_freeze(tmp_path: Path) -> None:
    source_root, private_root, manifest = _frozen_run(tmp_path)
    candidate = next(source_root.glob("sessions/**/*.jsonl"))
    candidate.write_bytes(candidate.read_bytes() + b'{"type":"extra"}\n')

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    assert error.value.code in {
        "full_persona_source_changed",
        "full_persona_source_universe_changed",
    }
