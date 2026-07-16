from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactEntry, StudyArtifactIndex
from ynoy.persona_study.artifact_contract import (
    ArtifactPayload as ArtifactPayload,
)
from ynoy.persona_study.artifact_contract import (
    artifact_entry,
)
from ynoy.persona_study.artifact_deletion import delete_run_locked, delete_source_closure
from ynoy.persona_study.artifact_mutations import (
    append_artifacts_locked,
    seal_mutable_locked,
    write_new_run,
)
from ynoy.persona_study.retention import (
    ExpiryPurgeResult,
    purge_expired_storage,
    require_complete_purge,
)
from ynoy.persona_study.storage_paths import StudyStoragePaths, require_regular_file
from ynoy.persona_study.transactions import (
    exclusive_study_lock,
    exclusive_write_bytes,
    require_index_matches_disk,
)
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes, sha256_bytes, utc_now


class PersonaStudyStore:
    def __init__(self, root: Path, *, real_data: bool, evaluation_time: datetime | None = None):
        assessment = require_private_root(root, real_data=real_data)
        self.root = assessment.root
        self.paths = StudyStoragePaths(self.root)
        self.runs = self.paths.control_root
        self.scoped_run_roots = (
            self.paths.control_root,
            self.paths.annotator_root,
            self.paths.evaluator_root,
        )
        self.tombstones = self.paths.tombstones
        self.evaluation_time = evaluation_time

    def write_run(
        self,
        study_id: str,
        payloads: tuple[ArtifactPayload, ...],
        *,
        created_at: datetime,
        expires_at: datetime,
    ) -> StudyArtifactIndex:
        access_time = self.evaluation_time or utc_now()
        require_complete_purge(self.purge_expired(access_time))
        if expires_at <= access_time:
            raise DataValidationError(
                "persona_study_expired",
                "Refusing to write a private study whose retention already expired.",
            )
        with self.study_lock(study_id):
            return self._write_new_run(study_id, payloads, created_at, expires_at)

    def _write_new_run(
        self,
        study_id: str,
        payloads: tuple[ArtifactPayload, ...],
        created_at: datetime,
        expires_at: datetime,
    ) -> StudyArtifactIndex:
        return write_new_run(self, study_id, payloads, created_at, expires_at)

    def read_index(self, study_id: str) -> StudyArtifactIndex:
        require_complete_purge(self.purge_expired(self.evaluation_time or utc_now()))
        return self._read_index_unchecked(study_id)

    def _read_index_unchecked(self, study_id: str) -> StudyArtifactIndex:
        path = self.paths.index(study_id)
        try:
            if not path.exists() and not path.is_symlink():
                raise FileNotFoundError(path)
            require_regular_file(path)
            index = StudyArtifactIndex.model_validate_json(path.read_bytes())
            require_index_matches_disk(self.paths, index)
            self._verify_entries(study_id, index.entries)
            return index
        except FileNotFoundError as exc:
            raise DataValidationError(
                "persona_study_not_found", "The requested private persona-study run was not found."
            ) from exc
        except (OSError, ValidationError) as exc:
            raise DataValidationError(
                "persona_study_index_invalid", "The private persona-study index is invalid."
            ) from exc

    def read_artifact(
        self, study_id: str, relative_path: str, *, allow_user_draft: bool = False
    ) -> bytes:
        index = self.read_index(study_id)
        matches = tuple(item for item in index.entries if item.relative_path == relative_path)
        if len(matches) != 1:
            raise DataValidationError(
                "persona_study_artifact_unknown", "The requested study artifact is unavailable."
            )
        entry = matches[0]
        if entry.mutable_by != "none" and not allow_user_draft:
            raise DataValidationError(
                "persona_study_mutable_read_denied",
                "A represented-user draft requires the explicit draft reader.",
            )
        path = self.paths.artifact(study_id, relative_path)
        require_regular_file(path)
        content = path.read_bytes()
        if entry.mutable_by == "none" and sha256_bytes(content) != entry.sha256:
            raise DataValidationError(
                "persona_study_artifact_tampered", "A derived artifact failed hash validation."
            )
        return content

    def delete_source_closure(self, study_id: str, source_dependency: str) -> int:
        require_complete_purge(self.purge_expired(self.evaluation_time or utc_now()))
        with self.study_lock(study_id):
            return self._delete_source_closure_locked(study_id, source_dependency)

    def append_artifacts(
        self, study_id: str, payloads: tuple[ArtifactPayload, ...]
    ) -> StudyArtifactIndex:
        require_complete_purge(self.purge_expired(self.evaluation_time or utc_now()))
        with self.study_lock(study_id):
            return append_artifacts_locked(self, study_id, payloads)

    def _delete_source_closure_locked(self, study_id: str, source_dependency: str) -> int:
        return delete_source_closure(self, study_id, source_dependency)

    def delete_run(self, study_id: str) -> int:
        require_complete_purge(self.purge_expired(self.evaluation_time or utc_now()))
        with self.study_lock(study_id):
            return self._delete_run_locked(study_id)

    def _delete_run_locked(self, study_id: str) -> int:
        return delete_run_locked(self, study_id)

    def seal_mutable_artifact(
        self,
        study_id: str,
        mutable_path: str,
        payloads: tuple[ArtifactPayload, ...],
        *,
        expected_mutable_sha256: str,
    ) -> StudyArtifactIndex:
        require_complete_purge(self.purge_expired(self.evaluation_time or utc_now()))
        with self.study_lock(study_id):
            return self._seal_mutable_locked(
                study_id, mutable_path, payloads, expected_mutable_sha256
            )

    def _seal_mutable_locked(
        self,
        study_id: str,
        mutable_path: str,
        payloads: tuple[ArtifactPayload, ...],
        expected_mutable_sha256: str,
    ) -> StudyArtifactIndex:
        return seal_mutable_locked(self, study_id, mutable_path, payloads, expected_mutable_sha256)

    def purge_expired(self, evaluation_time: datetime) -> ExpiryPurgeResult:
        return purge_expired_storage(self, evaluation_time)

    def study_lock(self, study_id: str) -> AbstractContextManager[None]:
        return exclusive_study_lock(self.paths.lock(study_id))

    def require_absent(self, study_id: str) -> None:
        if not self.paths.run_is_absent(study_id):
            raise DataValidationError(
                "persona_study_delete_incomplete", "Derived deletion closure left artifacts behind."
            )

    def _verify_entries(self, study_id: str, entries: tuple[StudyArtifactEntry, ...]) -> None:
        for entry in entries:
            path = self.paths.artifact(study_id, entry.relative_path)
            require_regular_file(path)
            if entry.mutable_by == "none" and sha256_bytes(path.read_bytes()) != entry.sha256:
                raise DataValidationError(
                    "persona_study_artifact_tampered", "A derived artifact failed hash validation."
                )

    def _write_payloads(
        self, study_id: str, payloads: tuple[ArtifactPayload, ...]
    ) -> tuple[StudyArtifactEntry, ...]:
        entries: list[StudyArtifactEntry] = []
        try:
            for payload in payloads:
                path = self.paths.artifact(study_id, payload.relative_path)
                exclusive_write_bytes(path, payload.content)
                entries.append(artifact_entry(payload))
        except Exception:
            self._remove_entries(study_id, tuple(entries))
            raise
        return tuple(entries)

    def _remove_entries(self, study_id: str, entries: tuple[StudyArtifactEntry, ...]) -> None:
        for entry in entries:
            path = self.paths.artifact(study_id, entry.relative_path)
            require_regular_file(path)
            path.unlink()

    def _write_index(self, index: StudyArtifactIndex) -> None:
        atomic_write_bytes(
            self.paths.index(index.study_id), canonical_json_bytes(index.model_dump(mode="json"))
        )
