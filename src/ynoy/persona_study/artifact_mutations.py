from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactEntry, StudyArtifactIndex
from ynoy.persona_study.artifact_contract import (
    ArtifactPayload,
    artifact_index,
    mutable_entry,
    require_unique_payloads,
)
from ynoy.persona_study.storage_paths import StudyStoragePaths, require_regular_file
from ynoy.persona_study.transactions import exclusive_write_bytes
from ynoy.util import canonical_json_bytes, sha256_bytes


class MutationStore(Protocol):
    paths: StudyStoragePaths

    def _read_index_unchecked(self, study_id: str) -> StudyArtifactIndex: ...

    def _verify_entries(self, study_id: str, entries: tuple[StudyArtifactEntry, ...]) -> None: ...

    def _write_payloads(
        self, study_id: str, payloads: tuple[ArtifactPayload, ...]
    ) -> tuple[StudyArtifactEntry, ...]: ...

    def _remove_entries(self, study_id: str, entries: tuple[StudyArtifactEntry, ...]) -> None: ...

    def _write_index(self, index: StudyArtifactIndex) -> None: ...

    def require_absent(self, study_id: str) -> None: ...


def write_new_run(
    store: MutationStore,
    study_id: str,
    payloads: tuple[ArtifactPayload, ...],
    created_at: datetime,
    expires_at: datetime,
) -> StudyArtifactIndex:
    store.paths.ensure_run_absent(study_id)
    require_unique_payloads(payloads)
    entries: tuple[StudyArtifactEntry, ...] = ()
    try:
        entries = store._write_payloads(study_id, payloads)
        index = artifact_index(study_id, created_at, expires_at, entries)
        exclusive_write_bytes(
            store.paths.index(study_id), canonical_json_bytes(index.model_dump(mode="json"))
        )
        return index
    except Exception:
        store._remove_entries(study_id, entries)
        store.paths.remove_empty_run(study_id)
        raise


def delete_source_closure(store: MutationStore, study_id: str, source_dependency: str) -> int:
    index = store._read_index_unchecked(study_id)
    selected = tuple(
        item for item in index.entries if source_dependency in item.source_dependencies
    )
    if not selected:
        raise DataValidationError(
            "persona_study_dependency_unknown", "No derived artifact depends on that source."
        )
    store._verify_entries(study_id, selected)
    store._remove_entries(study_id, selected)
    remaining = tuple(item for item in index.entries if item not in selected)
    if remaining:
        store._write_index(artifact_index(study_id, index.created_at, index.expires_at, remaining))
    else:
        store.paths.index(study_id).unlink()
    store.paths.remove_empty_run(study_id)
    if not remaining:
        store.require_absent(study_id)
    return len(selected)


def delete_run_locked(store: MutationStore, study_id: str) -> int:
    index = store._read_index_unchecked(study_id)
    store._verify_entries(study_id, index.entries)
    store._remove_entries(study_id, index.entries)
    store.paths.index(study_id).unlink()
    store.paths.remove_empty_run(study_id)
    store.require_absent(study_id)
    return len(index.entries)


def seal_mutable_locked(
    store: MutationStore,
    study_id: str,
    mutable_path: str,
    payloads: tuple[ArtifactPayload, ...],
    expected_mutable_sha256: str,
) -> StudyArtifactIndex:
    index = store._read_index_unchecked(study_id)
    mutable = mutable_entry(index, mutable_path)
    immutable = tuple(item for item in index.entries if item != mutable)
    store._verify_entries(study_id, immutable)
    draft_path = store.paths.artifact(study_id, mutable_path)
    require_regular_file(draft_path)
    _require_expected_draft(draft_path, expected_mutable_sha256)
    require_unique_payloads(payloads)
    added: tuple[StudyArtifactEntry, ...] = ()
    index_committed = False
    try:
        added = store._write_payloads(study_id, payloads)
        _require_expected_draft(draft_path, expected_mutable_sha256)
        sealed = mutable.model_copy(
            update={"sha256": expected_mutable_sha256, "mutable_by": "none"}
        )
        updated = artifact_index(
            study_id, index.created_at, index.expires_at, (*immutable, sealed, *added)
        )
        store._write_index(updated)
        index_committed = True
        store._verify_entries(study_id, updated.entries)
        return updated
    except Exception:
        if index_committed:
            _restore_index_before_cleanup(store, index)
        store._remove_entries(study_id, added)
        store.paths.remove_empty_run(study_id)
        raise


def _require_expected_draft(path: Path, expected_sha256: str) -> None:
    if sha256_bytes(path.read_bytes()) != expected_sha256:
        raise DataValidationError(
            "persona_study_mutable_changed",
            "The represented-user draft changed during submission; nothing was sealed.",
        )


def _restore_index_before_cleanup(store: MutationStore, previous: StudyArtifactIndex) -> None:
    try:
        store._write_index(previous)
    except Exception as exc:
        raise DataValidationError(
            "persona_study_rollback_incomplete",
            "The committed study index could not be restored; new artifacts were preserved.",
        ) from exc
