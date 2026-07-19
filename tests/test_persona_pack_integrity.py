from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from support.persona_pack import built_pack

from ynoy.errors import DataValidationError
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.store import FullPersonaStore


def _write_pack(private_root: Path, pack):
    store = FullPersonaPackStore(private_root, synthetic=True)
    store.write_pack(pack)
    return store


def test_pack_round_trip_is_bound_to_complete_corpus_head(tmp_path: Path) -> None:
    _source, private_root, manifest, pack = built_pack(tmp_path)
    store = _write_pack(private_root, pack)

    loaded = store.read_pack(pack.run_id)
    assert loaded.pack_sha256 == pack.pack_sha256
    assert loaded.run_id == manifest.run_id
    assert loaded.source_head_sha256 == pack.source_head_sha256


def test_reader_rejects_tampered_or_incomplete_corpus_head(tmp_path: Path) -> None:
    _source, private_root, manifest, _pack = built_pack(tmp_path)
    corpus = FullPersonaStore(private_root, synthetic=True)
    head = corpus.read_head(manifest.run_id)
    shard = next(corpus.iter_shard_paths(manifest.run_id))
    original = shard.read_bytes()
    shard.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))

    with pytest.raises(DataValidationError):
        tuple(iter_verified_evidence(corpus, manifest, head))

    shard.write_bytes(original)
    pointer = corpus.run_path(manifest.run_id) / "head.json"
    pointer_data = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_data["revision"] = max(0, pointer_data["revision"] - 1)
    pointer.write_text(json.dumps(pointer_data), encoding="utf-8")
    with pytest.raises(DataValidationError):
        tuple(iter_verified_evidence(corpus, manifest, head))


def test_pack_rejects_stale_source_head_after_corpus_changes(tmp_path: Path) -> None:
    _source, private_root, _manifest, pack = built_pack(tmp_path)
    store = _write_pack(private_root, pack)
    corpus = FullPersonaStore(private_root, synthetic=True)
    pointer = corpus.run_path(pack.run_id) / "head.json"
    pointer_data = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_data["head_sha256"] = "0" * 64
    pointer.write_text(json.dumps(pointer_data), encoding="utf-8")

    with pytest.raises(DataValidationError):
        store.read_pack(pack.run_id)


def test_pack_read_rejects_tampered_source_shard_after_pack_write(tmp_path: Path) -> None:
    _source, private_root, _manifest, pack = built_pack(tmp_path)
    pack_store = _write_pack(private_root, pack)
    corpus = FullPersonaStore(private_root, synthetic=True)
    shard = next(corpus.iter_shard_paths(pack.run_id))
    original = shard.read_bytes()
    shard.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))

    with pytest.raises(DataValidationError):
        pack_store.read_pack(pack.run_id)


def test_pack_build_fails_after_source_manifest_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _source, private_root, manifest, _pack = built_pack(tmp_path)
    expired = manifest.expires_at + timedelta(seconds=1)
    monkeypatch.setattr("ynoy.full_persona.pack_builder.utc_now", lambda: expired)

    with pytest.raises(DataValidationError):
        build_deterministic_pack(private_root, manifest.run_id, synthetic=True)


def test_pack_read_fails_after_source_manifest_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _source, private_root, manifest, pack = built_pack(tmp_path)
    pack_store = _write_pack(private_root, pack)
    expired = manifest.expires_at + timedelta(seconds=1)
    monkeypatch.setattr("ynoy.full_persona.pack_store.utc_now", lambda: expired)

    with pytest.raises(DataValidationError):
        pack_store.read_pack(pack.run_id)
