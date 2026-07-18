from __future__ import annotations

from pathlib import Path

import pytest
from support.full_persona import prepared_full_persona_source

from ynoy.errors import DataValidationError
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore


def _run(tmp_path: Path) -> tuple[Path, Path, str]:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)
    return source_root, private_root, manifest.run_id


def test_resume_rejects_a_committed_shard_byte_flip(tmp_path: Path) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1024)
    shard = next(store.iter_shard_paths(run_id))
    content = bytearray(shard.read_bytes())
    content[0] ^= 1
    shard.write_bytes(content)

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1024)

    assert error.value.code == "full_persona_integrity_invalid"


@pytest.mark.parametrize("mode", ["delete", "tamper"], ids=["deleted", "tampered"])
def test_resume_rejects_invalid_completed_file_receipt(tmp_path: Path, mode: str) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    complete = scan_full_corpus(source_root, private_root, run_id, synthetic=True)
    receipt = store.run_path(run_id) / "files" / "00000000.json"
    assert complete.status == "complete" and receipt.is_file()

    if mode == "delete":
        receipt.unlink()
    else:
        receipt.write_bytes(b"{}")

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, run_id, synthetic=True)

    assert error.value.code == "full_persona_integrity_invalid"


def test_budget_too_small_leaves_frozen_head_unchanged(tmp_path: Path) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    before = store.read_head(run_id)

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1)

    assert error.value.code == "full_persona_scan_budget_too_small"
    assert store.read_head(run_id) == before
    assert tuple(store.iter_shard_paths(run_id)) == ()
