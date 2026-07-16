from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import DeletionProofReceipt, StudyArtifactIndex
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file


@dataclass(frozen=True, slots=True)
class ExpiryPurgeResult:
    deleted_artifact_count: int
    deleted_tombstone_count: int
    failed_run_count: int
    failed_tombstone_count: int

    @property
    def failed_count(self) -> int:
        return self.failed_run_count + self.failed_tombstone_count


class RetentionStore(Protocol):
    runs: Path
    scoped_run_roots: tuple[Path, Path, Path]
    tombstones: Path

    def _read_index_unchecked(self, study_id: str) -> StudyArtifactIndex: ...

    def _delete_run_locked(self, study_id: str) -> int: ...

    def study_lock(self, study_id: str) -> AbstractContextManager[None]: ...


def purge_expired_storage(store: RetentionStore, evaluation_time: datetime) -> ExpiryPurgeResult:
    deleted = 0
    run_ids, failed_runs = _discover_run_ids(store.scoped_run_roots)
    for study_id in sorted(run_ids):
        try:
            with store.study_lock(study_id):
                index = store._read_index_unchecked(study_id)
                if index.expires_at <= evaluation_time:
                    deleted += store._delete_run_locked(index.study_id)
        except DataValidationError:
            failed_runs += 1
    tombstones, failed_tombstones = _purge_tombstones(store.tombstones, evaluation_time)
    return ExpiryPurgeResult(deleted, tombstones, failed_runs, failed_tombstones)


def require_complete_purge(result: ExpiryPurgeResult) -> None:
    if result.failed_count:
        raise DataValidationError(
            "persona_study_expiry_purge_incomplete",
            "One or more private runs or tombstones could not be checked or expired safely.",
        )


def _purge_tombstones(root: Path, evaluation_time: datetime) -> tuple[int, int]:
    reject_link_if_present(root)
    if not root.exists():
        return 0, 0
    deleted = failed = 0
    for path in sorted(root.iterdir()):
        try:
            if path.suffix != ".json":
                raise DataValidationError(
                    "persona_study_tombstone_invalid",
                    "Tombstone storage contains an unrecognized artifact.",
                )
            require_regular_file(path)
            receipt = DeletionProofReceipt.model_validate_json(path.read_bytes())
            if receipt.expires_at <= evaluation_time:
                path.unlink()
                deleted += 1
        except (OSError, ValidationError, DataValidationError):
            failed += 1
    return deleted, failed


def _discover_run_ids(roots: tuple[Path, Path, Path]) -> tuple[set[str], int]:
    identifiers: set[str] = set()
    failed = 0
    for root in roots:
        try:
            reject_link_if_present(root)
            if not root.exists():
                continue
            if not root.is_dir():
                raise DataValidationError(
                    "persona_study_storage_invalid", "Study storage root is not a directory."
                )
            for path in root.iterdir():
                reject_link_if_present(path)
                if not path.is_dir():
                    failed += 1
                else:
                    identifiers.add(path.name)
        except (OSError, DataValidationError):
            failed += 1
    return identifiers, failed
