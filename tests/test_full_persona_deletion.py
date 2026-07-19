from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from support.persona_pack import prepared_pack_source

from ynoy.erasure_contract import build_default_registry
from ynoy.errors import DataValidationError
from ynoy.full_persona.deletion import delete_full_persona_run
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore


def _generated_run(tmp_path: Path) -> tuple[Path, Path, str]:
    source_root, private_root, prepared = prepared_pack_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    store = FullPersonaStore(private_root, synthetic=True)
    store.write_manifest(manifest)
    scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    pack = build_deterministic_pack(private_root, manifest.run_id, synthetic=True)
    FullPersonaPackStore(private_root, synthetic=True).write_pack(pack)
    return source_root, private_root, manifest.run_id


def test_delete_full_persona_run_removes_generated_closure_only(tmp_path: Path) -> None:
    source_root, private_root, run_id = _generated_run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    assert store.run_path(run_id).is_dir()
    assert tuple(store.iter_shard_paths(run_id))
    assert FullPersonaPackStore(private_root, synthetic=True).run_path(run_id).is_dir()

    deleted = delete_full_persona_run(private_root, run_id, synthetic=True)

    assert deleted > 0
    assert not store.run_path(run_id).exists()
    assert not FullPersonaPackStore(private_root, synthetic=True).run_path(run_id).exists()
    assert source_root.is_dir()
    with pytest.raises(DataValidationError):
        store.read_manifest(run_id)


def test_erasure_registry_declares_full_persona_artifact_producer() -> None:
    registry = build_default_registry()

    assert "artifact:full_persona_runs" in {item.producer_id for item in registry.producers}


def test_erasure_registry_declares_full_persona_pack_producer() -> None:
    registry = build_default_registry()

    assert "artifact:full_persona_packs" in {item.producer_id for item in registry.producers}


def test_pack_only_orphan_closure_can_be_deleted(tmp_path: Path) -> None:
    _source, private_root, run_id = _generated_run(tmp_path)
    corpus = FullPersonaStore(private_root, synthetic=True)
    pack_store = FullPersonaPackStore(private_root, synthetic=True)
    shutil.rmtree(corpus.run_path(run_id))
    assert not corpus.run_path(run_id).exists()
    assert pack_store.run_path(run_id).is_dir()

    deleted = delete_full_persona_run(private_root, run_id, synthetic=True)

    assert deleted > 0
    assert not pack_store.run_path(run_id).exists()
