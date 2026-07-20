from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import model_bytes, validate_digest
from ynoy.models.persona_reaction_artifact import PersonaReactionBenchmarkArtifact
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes

_MAX_ARTIFACT_BYTES = 8 * 1024**2
_MAX_POINTER_BYTES = 4 * 1024


class FullPersonaReactionStore:
    def __init__(self, root: Path):
        self.root = require_private_root(root, real_data=True).root
        self.base = self.root / "full-persona-packs"
        reject_link_if_present(self.base)

    def write(self, artifact: PersonaReactionBenchmarkArtifact) -> Path:
        self._validate(artifact)
        content = model_bytes(artifact)
        if len(content) > _MAX_ARTIFACT_BYTES:
            _store_error("reaction artifact exceeded its byte limit")
        directory = self._directory(artifact.source_run_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = self._path(artifact.source_run_id, artifact.artifact_id)
        if path.exists():
            existing = self._read_path(path)
            if existing.artifact_sha256 != artifact.artifact_sha256:
                _store_error("a different reaction artifact owns this identifier")
        else:
            atomic_write_bytes(path, content)
        atomic_write_bytes(
            self._pointer(artifact.source_run_id),
            canonical_json_bytes(
                {
                    "artifact_id": artifact.artifact_id,
                    "artifact_sha256": artifact.artifact_sha256,
                }
            ),
        )
        return path

    def read(self, run_id: str) -> PersonaReactionBenchmarkArtifact:
        try:
            pointer = json.loads(_read_bounded(self._pointer(run_id), _MAX_POINTER_BYTES))
            artifact_id = pointer["artifact_id"]
            expected = pointer["artifact_sha256"]
            if not isinstance(artifact_id, str) or not isinstance(expected, str):
                raise ValueError
            validate_digest(artifact_id)
            validate_digest(expected)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise DataValidationError(
                "reaction_artifact_pointer_invalid", "The reaction artifact pointer is invalid."
            ) from exc
        artifact = self._read_path(self._path(run_id, artifact_id))
        if artifact.artifact_sha256 != expected:
            _store_error("reaction artifact pointer is stale")
        self._validate(artifact)
        return artifact

    def _validate(self, artifact: PersonaReactionBenchmarkArtifact) -> None:
        try:
            checked = PersonaReactionBenchmarkArtifact.model_validate(
                artifact.model_dump(mode="json")
            )
        except (AttributeError, ValidationError) as exc:
            raise DataValidationError(
                "reaction_artifact_invalid", "The private reaction artifact is invalid."
            ) from exc
        store = FullPersonaStore(self.root, synthetic=False)
        manifest = store.read_manifest(checked.source_run_id)
        head = store.read_head(checked.source_run_id)
        verify_committed_run(store, manifest, head)
        if (
            manifest.manifest_sha256 != checked.source_manifest_sha256
            or head.head_sha256 != checked.source_head_sha256
            or head.revision != checked.source_head_revision
            or head.status != "complete"
        ):
            _store_error("reaction artifact source head is stale")

    def _read_path(self, path: Path) -> PersonaReactionBenchmarkArtifact:
        try:
            return PersonaReactionBenchmarkArtifact.model_validate_json(
                _read_bounded(path, _MAX_ARTIFACT_BYTES)
            )
        except (OSError, ValidationError, ValueError) as exc:
            raise DataValidationError(
                "reaction_artifact_invalid", "The private reaction artifact is invalid."
            ) from exc

    def _directory(self, run_id: str) -> Path:
        validate_digest(run_id)
        return self._safe(self.base / run_id / "reaction")

    def _path(self, run_id: str, artifact_id: str) -> Path:
        validate_digest(artifact_id)
        return self._safe(self._directory(run_id) / f"{artifact_id}.json")

    def _pointer(self, run_id: str) -> Path:
        return self._safe(self._directory(run_id) / "latest.json")

    def _safe(self, path: Path) -> Path:
        try:
            relative = path.relative_to(self.base)
        except ValueError as exc:
            raise DataValidationError(
                "reaction_artifact_path_escape", "A reaction artifact escaped private storage."
            ) from exc
        current = self.base
        for part in relative.parts:
            current /= part
            reject_link_if_present(current)
        return path


def _read_bounded(path: Path, limit: int) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        _store_error("reaction artifact exceeded its byte limit")
    return content


def _store_error(reason: str) -> None:
    raise DataValidationError(
        "reaction_artifact_store_invalid",
        "The private reaction artifact failed closed.",
        details={"reason": reason},
    )
