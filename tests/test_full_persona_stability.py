from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from support.full_persona import add_large_canonical_file, prepared_full_persona_source

from ynoy.corpus.codex_discovery import CodexInventoryLimits, discover_codex_sessions
from ynoy.errors import DataValidationError
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import FullCorpusLimits


def _frozen_run(tmp_path: Path):
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    mutable_candidate = sorted(source_root.glob("sessions/**/*.jsonl"))[20]
    now_ns = time.time_ns()
    os.utime(mutable_candidate, ns=(now_ns, now_ns))
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)
    return source_root, private_root, manifest


def _source_path(source_root: Path, locator: str, partition: str = "sessions") -> Path:
    return source_root / partition / Path(locator)


def _excluded(manifest, reason: str):
    return next(item for item in manifest.excluded_files if item.reason == reason)


def test_discovery_filters_post_boundary_before_stat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root, _private_root, prepared = prepared_full_persona_source(tmp_path)
    post_boundary = Path(os.path.abspath(sorted(source_root.glob("sessions/**/*.jsonl"))[-1]))
    observed: list[Path] = []
    original_stat = os.stat

    def guarded_stat(path, *args, **kwargs):
        resolved = Path(os.path.abspath(os.fspath(path)))
        if resolved == post_boundary:
            raise AssertionError("post-boundary canonical file was stat'ed")
        observed.append(resolved)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr("ynoy.corpus.codex_discovery.os.stat", guarded_stat)
    boundary_ns = int(prepared.manifest.cutoff.timestamp() * 1_000_000_000)
    discovery = discover_codex_sessions(
        source_root,
        CodexInventoryLimits(),
        session_start_before_ns=boundary_ns,
    )

    assert post_boundary not in {item.path.resolve() for item in discovery.files}
    assert post_boundary not in observed


def test_post_boundary_active_mutation_is_ignored_by_freeze(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    post_boundary = sorted(source_root.glob("sessions/**/*.jsonl"))[-1]
    post_boundary.write_bytes(post_boundary.read_bytes() + b"active post-boundary write\n")

    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )

    locator = post_boundary.relative_to(source_root / "sessions").as_posix()
    assert locator not in {item.relative_locator for item in manifest.files}
    assert locator not in {item.relative_locator for item in manifest.excluded_files}


def test_old_named_post_cutoff_file_is_explicitly_excluded(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    old_named = sorted(source_root.glob("sessions/**/*.jsonl"))[20]
    now_ns = time.time_ns()
    os.utime(old_named, ns=(now_ns, now_ns))
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )

    exclusion = _excluded(manifest, "modified_after_stability_cutoff")
    assert exclusion.relative_locator
    assert exclusion.observed_file_bytes > 0
    assert manifest.expected_excluded_file_count == len(manifest.excluded_files)
    assert manifest.stable_before_ns < exclusion.observed_modified_ns
    assert manifest.stable_before_ns < manifest.holdout_boundary_session_start_ns
    assert all(item.modified_ns <= manifest.stable_before_ns for item in manifest.files)


def test_included_pre_cutoff_mutation_is_rejected_on_scan(tmp_path: Path) -> None:
    source_root, private_root, manifest = _frozen_run(tmp_path)
    source = manifest.files[0]
    path = _source_path(source_root, source.relative_locator, source.partition)
    path.write_bytes(path.read_bytes() + b"included source mutation\n")

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    assert error.value.code in {
        "full_persona_source_changed",
        "full_persona_source_universe_changed",
    }


def test_same_size_content_mutation_after_verification_commits_no_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    large = add_large_canonical_file(source_root, size=128 * 1024 + 257)
    limits = FullCorpusLimits(source_chunk_bytes=64 * 1024)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True, limits=limits
    )
    source = next(
        item
        for item in manifest.files
        if item.relative_locator == large.relative_to(source_root / "sessions").as_posix()
    )
    path = _source_path(source_root, source.relative_locator, source.partition)
    original_bytes = path.read_bytes()
    original_mtime_ns = path.stat().st_mtime_ns
    mutation_offset = limits.source_chunk_bytes
    replacement = bytearray(original_bytes)
    replacement[mutation_offset] ^= 1
    replacement = bytes(replacement)
    assert replacement != original_bytes and len(replacement) == len(original_bytes)
    import ynoy.full_persona.chunk_stream as chunk_module

    read_verified_chunk = chunk_module._read_verified_chunk
    mutated = False

    def mutate_after_first_verified_read(*args, **kwargs):
        nonlocal mutated
        result = read_verified_chunk(*args, **kwargs)
        chunk_index = kwargs.get("chunk_index", args[2] if len(args) > 2 else None)
        if chunk_index == 0 and not mutated:
            mutated = True
            path.write_bytes(replacement)
            os.utime(path, ns=(original_mtime_ns, original_mtime_ns))
        return result

    monkeypatch.setattr(chunk_module, "_read_verified_chunk", mutate_after_first_verified_read)
    store = FullPersonaStore(private_root, synthetic=True)
    store.write_manifest(manifest)
    before = store.read_head(manifest.run_id)

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    assert error.value.code == "full_persona_source_chunk_changed"
    assert store.read_head(manifest.run_id) == before
    assert tuple(store.iter_shard_paths(manifest.run_id)) == ()


def test_manifest_control_cap_rejects_before_private_persistence(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    limits = FullCorpusLimits(source_chunk_bytes=64 * 1024, max_manifest_control_bytes=1024)

    with pytest.raises(DataValidationError) as error:
        manifest = freeze_full_corpus(
            source_root,
            private_root,
            prepared.manifest.study_id,
            synthetic=True,
            limits=limits,
        )
        FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)

    assert error.value.code in {
        "full_persona_manifest_oversized",
        "full_persona_manifest_control_oversized",
        "full_persona_control_oversized",
    }
    assert not (private_root / "full-persona-runs").exists()


def test_exclusion_manifest_tamper_is_rejected_by_store(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    old_named = sorted(source_root.glob("sessions/**/*.jsonl"))[20]
    now_ns = time.time_ns()
    os.utime(old_named, ns=(now_ns, now_ns))
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    assert manifest.excluded_files
    tampered = manifest.model_copy(update={"exclusion_snapshot_sha256": "0" * 64})

    with pytest.raises(DataValidationError) as error:
        FullPersonaStore(private_root, synthetic=True).write_manifest(tampered)

    assert error.value.code == "full_persona_manifest_invalid"


def test_scan_accepts_mutating_exclusion_but_rejects_membership_change(tmp_path: Path) -> None:
    source_root, private_root, manifest = _frozen_run(tmp_path)
    exclusion = _excluded(manifest, "modified_after_stability_cutoff")
    excluded_path = _source_path(source_root, exclusion.relative_locator, exclusion.partition)
    excluded_path.write_bytes(excluded_path.read_bytes() + b"continuing mutable exclusion\n")

    complete = scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    assert complete.status == "complete"

    source_root, private_root, manifest = _frozen_run(tmp_path / "membership")
    exclusion = _excluded(manifest, "modified_after_stability_cutoff")
    excluded_path = _source_path(source_root, exclusion.relative_locator, exclusion.partition)
    stable_ns = manifest.stable_before_ns
    os.utime(excluded_path, ns=(stable_ns, stable_ns))

    with pytest.raises(DataValidationError) as error:
        scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)

    assert error.value.code in {
        "full_persona_source_universe_changed",
        "full_persona_exclusion_changed",
    }


def test_empty_pre_boundary_file_is_explicitly_excluded(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    empty = (
        source_root
        / "sessions"
        / "2025"
        / "12"
        / "30"
        / ("rollout-2025-12-30T03-04-05-00000000-0000-0000-0000-000000000001.jsonl")
    )
    empty.parent.mkdir(parents=True)
    empty.touch()
    stable_ns = int(prepared.manifest.cutoff.timestamp() * 1_000_000_000)
    os.utime(empty, ns=(stable_ns, stable_ns))

    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )

    assert any(
        item.relative_locator == empty.relative_to(source_root / "sessions").as_posix()
        and item.reason == "empty_at_freeze"
        for item in manifest.excluded_files
    )
