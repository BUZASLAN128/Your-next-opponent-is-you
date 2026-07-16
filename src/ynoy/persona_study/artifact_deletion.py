from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactEntry, StudyArtifactIndex
from ynoy.persona_study.artifact_contract import artifact_index
from ynoy.persona_study.storage_paths import StudyStoragePaths, require_regular_file
from ynoy.util import atomic_write_bytes, canonical_json_bytes


class DeletionStore(Protocol):
    paths: StudyStoragePaths

    def _read_index_unchecked(self, study_id: str) -> StudyArtifactIndex: ...

    def _verify_entries(self, study_id: str, entries: tuple[StudyArtifactEntry, ...]) -> None: ...

    def _write_index(self, index: StudyArtifactIndex) -> None: ...

    def require_absent(self, study_id: str) -> None: ...


def delete_source_closure(store: DeletionStore, study_id: str, dependency: str) -> int:
    index = store._read_index_unchecked(study_id)
    selected = tuple(item for item in index.entries if dependency in item.source_dependencies)
    if not selected:
        raise DataValidationError(
            "persona_study_dependency_unknown", "No derived artifact depends on that source."
        )
    store._verify_entries(study_id, selected)
    staged = _stage_entries(store, study_id, selected)
    remaining = tuple(item for item in index.entries if item not in selected)
    try:
        if remaining:
            store._write_index(
                artifact_index(study_id, index.created_at, index.expires_at, remaining)
            )
        else:
            store.paths.index(study_id).unlink()
            store.paths.remove_empty_run(study_id)
            store.require_absent(study_id)
    except Exception:
        _rollback_delete(store, index, staged)
        raise
    _discard_staged(staged)
    return len(selected)


def delete_run_locked(store: DeletionStore, study_id: str) -> int:
    index = store._read_index_unchecked(study_id)
    store._verify_entries(study_id, index.entries)
    staged = _stage_entries(store, study_id, index.entries)
    try:
        store.paths.index(study_id).unlink()
        store.paths.remove_empty_run(study_id)
        store.require_absent(study_id)
    except Exception:
        _rollback_delete(store, index, staged)
        raise
    _discard_staged(staged)
    return len(index.entries)


def _stage_entries(
    store: DeletionStore, study_id: str, entries: tuple[StudyArtifactEntry, ...]
) -> tuple[tuple[Path, Path], ...]:
    if not entries:
        return ()
    staging = store.paths.tombstones / f".pending-delete-{uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    moved: list[tuple[Path, Path]] = []
    try:
        for position, entry in enumerate(entries):
            original = store.paths.artifact(study_id, entry.relative_path)
            require_regular_file(original)
            target = staging / f"{position:08d}.blob"
            original.replace(target)
            moved.append((original, target))
    except Exception:
        if moved:
            _restore_staged(tuple(moved))
        elif staging.exists():
            staging.rmdir()
        raise
    return tuple(moved)


def _rollback_delete(
    store: DeletionStore,
    index: StudyArtifactIndex,
    staged: tuple[tuple[Path, Path], ...],
) -> None:
    try:
        index_path = store.paths.index(index.study_id)
        expected = canonical_json_bytes(index.model_dump(mode="json"))
        if not index_path.exists() or index_path.read_bytes() != expected:
            atomic_write_bytes(index_path, expected)
        _restore_staged(staged)
        store.paths.remove_empty_run(index.study_id)
    except Exception as exc:
        raise DataValidationError(
            "persona_study_delete_rollback_incomplete",
            "A failed artifact deletion could not restore its index and files.",
        ) from exc


def _restore_staged(staged: tuple[tuple[Path, Path], ...]) -> None:
    staging = staged[0][1].parent if staged else None
    for original, temporary in reversed(staged):
        original.parent.mkdir(parents=True, exist_ok=True)
        if temporary.exists():
            temporary.replace(original)
    if staging is not None and staging.exists():
        staging.rmdir()


def _discard_staged(staged: tuple[tuple[Path, Path], ...]) -> None:
    staging = staged[0][1].parent if staged else None
    try:
        for _, temporary in staged:
            temporary.unlink()
        if staging is not None:
            staging.rmdir()
    except Exception as exc:
        raise DataValidationError(
            "persona_study_delete_cleanup_incomplete",
            "The artifact index was updated but staged private bytes remain for cleanup.",
        ) from exc
