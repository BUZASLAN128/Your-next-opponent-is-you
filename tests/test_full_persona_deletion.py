from __future__ import annotations

from pathlib import Path

import pytest
from support.full_persona import prepared_full_persona_source

from ynoy.erasure_contract import build_default_registry
from ynoy.errors import DataValidationError
from ynoy.full_persona.deletion import delete_full_persona_run
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore


def _generated_run(tmp_path: Path) -> tuple[Path, Path, str]:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    store = FullPersonaStore(private_root, synthetic=True)
    store.write_manifest(manifest)
    scan_full_corpus(
        source_root,
        private_root,
        manifest.run_id,
        synthetic=True,
        max_input_bytes=1024,
    )
    return source_root, private_root, manifest.run_id


def test_delete_full_persona_run_removes_generated_closure_only(tmp_path: Path) -> None:
    source_root, private_root, run_id = _generated_run(tmp_path)
    store = FullPersonaStore(private_root, synthetic=True)
    assert store.run_path(run_id).is_dir()
    assert tuple(store.iter_shard_paths(run_id))

    deleted = delete_full_persona_run(private_root, run_id, synthetic=True)

    assert deleted > 0
    assert not store.run_path(run_id).exists()
    assert source_root.is_dir()
    with pytest.raises(DataValidationError):
        store.read_manifest(run_id)


def test_erasure_registry_declares_full_persona_artifact_producer() -> None:
    registry = build_default_registry()

    assert "artifact:full_persona_runs" in {item.producer_id for item in registry.producers}
