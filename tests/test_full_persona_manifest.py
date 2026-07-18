from __future__ import annotations

from pathlib import Path

import pytest
from support.full_persona import add_large_canonical_file, prepared_full_persona_source
from ynoy.full_persona.store import FullPersonaStore

from ynoy.errors import DataValidationError
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.models.full_persona import FullCorpusLimits


def test_full_corpus_limits_keep_line_and_wire_caps_coherent() -> None:
    with pytest.raises(ValueError, match="wire-record"):
        FullCorpusLimits(max_line_bytes=17, max_wire_record_bytes=16)

    limits = FullCorpusLimits(max_line_bytes=16, max_wire_record_bytes=32)
    assert limits.max_line_bytes == 16
    assert limits.max_wire_record_bytes == 32


def test_freeze_includes_large_pre_holdout_file_and_reuses_existing_holdout(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    large = add_large_canonical_file(source_root)

    manifest = freeze_full_corpus(
        source_root,
        private_root,
        prepared.manifest.study_id,
        synthetic=True,
    )

    assert manifest.source_study_id == prepared.manifest.study_id
    assert manifest.holdout_freeze_sha256 == prepared.manifest.protected_holdout_freeze_sha256
    assert manifest.expected_input_bytes == sum(item.file_bytes for item in manifest.files)
    assert any(item.file_bytes == large.stat().st_size for item in manifest.files)
    assert manifest.manifest_sha256


def test_freeze_replays_identically_for_fixed_synthetic_source(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    first = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    second = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_manifest_store_rejects_resealed_semantic_mutation(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    store = FullPersonaStore(private_root, synthetic=True)
    store.write_manifest(manifest)
    tampered = manifest.model_copy(
        update={"expected_input_bytes": manifest.expected_input_bytes + 1}
    )

    with pytest.raises(DataValidationError):
        store.write_manifest(tampered)


def test_freeze_rejects_missing_or_wrong_source_study(tmp_path: Path) -> None:
    source_root, private_root, _prepared = prepared_full_persona_source(tmp_path)

    with pytest.raises(DataValidationError):
        freeze_full_corpus(source_root, private_root, "0" * 64, synthetic=True)
