from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import model_bytes, validate_digest
from ynoy.models.persona_life_profile import PersonaLifeProfile
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes, utc_now

_MAX_PROFILE_BYTES = 2 * 1024**2
_MAX_POINTER_BYTES = 4 * 1024


class FullPersonaLifeProfileStore:
    def __init__(self, root: Path, *, synthetic: bool):
        self.root = require_private_root(root, real_data=not synthetic).root
        self.synthetic = synthetic
        self.base = self.root / "full-persona-packs"
        reject_link_if_present(self.base)

    def write(self, profile: PersonaLifeProfile) -> Path:
        self._validate(profile)
        content = model_bytes(profile)
        if len(content) > _MAX_PROFILE_BYTES:
            _store_error("life profile exceeded its byte limit")
        directory = self._directory(profile.source_run_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = self._path(profile.source_run_id, profile.profile_id)
        if path.exists():
            existing = self._read_path(path)
            if existing.profile_sha256 != profile.profile_sha256:
                _store_error("a different life profile owns this identifier")
        else:
            atomic_write_bytes(path, content)
        atomic_write_bytes(
            self._pointer(profile.source_run_id),
            canonical_json_bytes(
                {"profile_id": profile.profile_id, "profile_sha256": profile.profile_sha256}
            ),
        )
        return path

    def read(self, run_id: str) -> PersonaLifeProfile:
        try:
            pointer = json.loads(_read_bounded(self._pointer(run_id), _MAX_POINTER_BYTES))
            profile_id = pointer["profile_id"]
            expected = pointer["profile_sha256"]
            if not isinstance(profile_id, str) or not isinstance(expected, str):
                raise ValueError
            validate_digest(profile_id)
            validate_digest(expected)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise DataValidationError(
                "life_profile_pointer_invalid", "The life-profile pointer is invalid."
            ) from exc
        profile = self._read_path(self._path(run_id, profile_id))
        if profile.profile_sha256 != expected:
            _store_error("life profile pointer is stale")
        self._validate(profile)
        return profile

    def _validate(self, profile: PersonaLifeProfile) -> None:
        try:
            checked = PersonaLifeProfile.model_validate(profile.model_dump(mode="json"))
        except (AttributeError, ValidationError) as exc:
            raise DataValidationError(
                "life_profile_invalid", "The private life profile is invalid."
            ) from exc
        if checked.synthetic != self.synthetic or checked.expires_at <= utc_now():
            _store_error("life profile mode or retention is invalid")
        source = FullPersonaStore(self.root, synthetic=self.synthetic)
        manifest = source.read_manifest(checked.source_run_id)
        head = source.read_head(checked.source_run_id)
        verify_committed_run(source, manifest, head)
        if (
            manifest.manifest_sha256 != checked.source_manifest_sha256
            or head.head_sha256 != checked.source_head_sha256
            or head.revision != checked.source_head_revision
            or head.evidence_count != checked.scanned_evidence_count
            or head.status != "complete"
        ):
            _store_error("life profile source head is stale")

    def _read_path(self, path: Path) -> PersonaLifeProfile:
        try:
            return PersonaLifeProfile.model_validate_json(_read_bounded(path, _MAX_PROFILE_BYTES))
        except (OSError, ValidationError, ValueError) as exc:
            raise DataValidationError(
                "life_profile_invalid", "The private life profile is invalid."
            ) from exc

    def _directory(self, run_id: str) -> Path:
        validate_digest(run_id)
        return self._safe(self.base / run_id / "life-profile")

    def _path(self, run_id: str, profile_id: str) -> Path:
        validate_digest(profile_id)
        return self._safe(self._directory(run_id) / f"{profile_id}.json")

    def _pointer(self, run_id: str) -> Path:
        return self._safe(self._directory(run_id) / "latest.json")

    def _safe(self, path: Path) -> Path:
        try:
            relative = path.relative_to(self.base)
        except ValueError as exc:
            raise DataValidationError(
                "life_profile_path_escape", "A life profile escaped private storage."
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
        _store_error("life profile exceeded its byte limit")
    return content


def _store_error(reason: str) -> None:
    raise DataValidationError(
        "life_profile_store_invalid",
        "The private life profile failed closed.",
        details={"reason": reason},
    )
