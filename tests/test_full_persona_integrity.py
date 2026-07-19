from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.full_persona import prepared_full_persona_source

from ynoy.errors import DataValidationError
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import seal_full_corpus_head
from ynoy.util import canonical_sha256


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


def test_resume_recovers_only_tail_artifacts_after_authoritative_pointer(
    tmp_path: Path,
) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1024)
    tail = _write_commit_tail(store, run_id)
    candidate_head, staging = tail
    candidate_bytes = candidate_head.read_bytes()

    complete = scan_full_corpus(source_root, private_root, run_id, synthetic=True)

    assert complete.status == "complete"
    assert candidate_head.exists()
    assert candidate_head.read_bytes() != candidate_bytes
    assert not staging.exists()
    pointer = json.loads((store.run_path(run_id) / "head.json").read_text(encoding="utf-8"))
    assert pointer == {"revision": complete.revision, "head_sha256": complete.head_sha256}


def test_resume_rejects_shard_receipt_revision_not_matching_filename(
    tmp_path: Path,
) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1024)
    shard = next(store.iter_shard_paths(run_id))
    receipt_path = shard.with_suffix(".receipt.json")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["revision"] += 1
    payload["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "receipt_sha256"}
    )
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, run_id, synthetic=True)

    assert error.value.code == "full_persona_integrity_invalid"


def test_resume_rejects_tampered_authoritative_pointer(tmp_path: Path) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    head = store.read_head(run_id)
    pointer = store.run_path(run_id) / "head.json"
    pointer.write_text(
        json.dumps({"revision": head.revision, "head_sha256": "0" * 64}),
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, run_id, synthetic=True)

    assert error.value.code == "full_persona_head_binding_invalid"


def test_full_persona_run_lock_is_exclusive_and_reusable(tmp_path: Path) -> None:
    _source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)

    with store.lock(run_id):
        with pytest.raises(DataValidationError) as error:
            with store.lock(run_id):
                pass
        assert error.value.code == "persona_study_locked"

    with store.lock(run_id):
        pass


def test_unknown_artifact_is_not_removed_during_recovery(tmp_path: Path) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1024)
    unknown = store.run_path(run_id) / "operator-note.txt"
    unknown.write_text("do not delete", encoding="utf-8")

    with pytest.raises(DataValidationError):
        scan_full_corpus(source_root, private_root, run_id, synthetic=True)

    assert unknown.read_text(encoding="utf-8") == "do not delete"


def test_malformed_tail_head_is_preserved_and_fails_closed(tmp_path: Path) -> None:
    source_root, private_root, run_id = _run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    scan_full_corpus(source_root, private_root, run_id, synthetic=True, max_input_bytes=1024)
    head = store.read_head(run_id)
    malformed = store.run_path(run_id) / "heads" / f"{head.revision + 1:08d}.json"
    malformed.write_bytes(b"not-json")

    with pytest.raises(DataValidationError):
        scan_full_corpus(source_root, private_root, run_id, synthetic=True)

    assert malformed.read_bytes() == b"not-json"


def _write_commit_tail(store: FullPersonaStore, run_id: str) -> tuple[Path, ...]:
    current = store.read_head(run_id)
    run = store.run_path(run_id)
    revision = current.revision + 1
    tail_head_path = run / "heads" / f"{revision:08d}.json"
    head_payload = current.model_dump(mode="python", exclude={"head_sha256"})
    head_payload["revision"] = revision
    head_payload["previous_head_sha256"] = current.head_sha256
    tail_head = seal_full_corpus_head(head_payload)
    tail_head_path.write_bytes(tail_head.model_dump_json().encode())

    staging = store.new_staging_path(run_id)
    staging.write_bytes(b"generated tail")
    return (tail_head_path, staging)
