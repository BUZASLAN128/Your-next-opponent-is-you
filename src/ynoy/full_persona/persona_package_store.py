from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.store_contract import model_bytes, validate_digest
from ynoy.models.persona_package import (
    FullPersonaPackage,
    PersonaPackageInspection,
    PersonaPackageProtocol,
)
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.util import atomic_write_bytes, canonical_json_bytes, canonical_sha256, utc_now

_MAX_PACKAGE_BYTES = 2 * 1024**2
_MAX_ATLAS_BYTES = 512 * 1024
_MAX_POINTER_BYTES = 4 * 1024


class FullPersonaPackageStore:
    """Immutable private package projections colocated with their source pack generation."""

    def __init__(self, root: Path, *, synthetic: bool):
        self.pack_store = FullPersonaPackStore(root, synthetic=synthetic)
        self.synthetic = synthetic

    def write_package(self, package: FullPersonaPackage) -> Path:
        self._validate(package)
        encoded = model_bytes(package)
        if len(encoded) > _MAX_PACKAGE_BYTES:
            _store_error("persona package exceeded its bounded artifact size")
        run = self.pack_store.run_path(package.source_run_id)
        run.mkdir(parents=True, exist_ok=True)
        path = self._path(package.source_run_id, package.package_id)
        if path.exists():
            existing = self._read_path(path)
            if existing.package_sha256 != package.package_sha256:
                _store_error("a different package owns this identifier")
        else:
            atomic_write_bytes(path, encoded)
        atomic_write_bytes(
            self._pointer(package.source_run_id),
            canonical_json_bytes(
                {
                    "package_id": package.package_id,
                    "package_sha256": package.package_sha256,
                }
            ),
        )
        return path

    def write_brain_atlas(self, package: FullPersonaPackage, content: str) -> Path:
        """Persist a bounded private Markdown projection beside its canonical package."""
        self._validate(package)
        encoded = content.encode("utf-8")
        if not encoded or len(encoded) > _MAX_ATLAS_BYTES:
            _store_error("persona brain atlas exceeded its bounded artifact size")
        path = self._safe(
            self.pack_store.run_path(package.source_run_id) / f"{package.package_id}.brain-atlas.md"
        )
        if path.exists():
            if _read_bounded(path, _MAX_ATLAS_BYTES) != encoded:
                _store_error("a different brain atlas owns this package identifier")
        else:
            atomic_write_bytes(path, encoded)
        return path

    def read_package(self, run_id: str, package_id: str | None = None) -> FullPersonaPackage:
        selected, expected = self._selected(run_id, package_id)
        package = self._read_path(self._path(run_id, selected))
        if expected is not None and package.package_sha256 != expected:
            _store_error("persona package pointer is stale")
        self._validate(package)
        return package

    def inspect_package(
        self, run_id: str, package_id: str | None = None
    ) -> PersonaPackageInspection:
        """Classify current or immutable legacy packages without enabling legacy review."""
        selected, expected = self._selected(run_id, package_id)
        path = self._path(run_id, selected)
        try:
            payload = json.loads(_read_bounded(path, _MAX_PACKAGE_BYTES))
            if not isinstance(payload, dict):
                raise ValueError
            protocol = payload.get("protocol_version")
            if protocol == "full-persona-package/0.3":
                package = FullPersonaPackage.model_validate(payload)
                self._validate(package)
                _require_pointer_hash(package.package_sha256, expected)
                return _inspection(
                    package.protocol_version, package.package_id, package.package_sha256
                )
            if protocol == "full-persona-package/0.2":
                return self._inspect_legacy(run_id, payload, expected)
            raise ValueError
        except (KeyError, OSError, TypeError, ValidationError, ValueError) as exc:
            raise DataValidationError(
                "persona_package_inspection_invalid",
                "The private persona package could not be safely inspected.",
            ) from exc

    def _inspect_legacy(
        self, run_id: str, payload: dict[str, object], expected: str | None
    ) -> PersonaPackageInspection:
        package_id = _digest_field(payload, "package_id")
        package_sha256 = _digest_field(payload, "package_sha256")
        pack_id = _digest_field(payload, "pack_id")
        pack_sha256 = _digest_field(payload, "pack_sha256")
        if "adjudication" in payload or payload.get("source_run_id") != run_id:
            raise ValueError("legacy package classification is inconsistent")
        canonical_payload = {
            key: value for key, value in payload.items() if key != "package_sha256"
        }
        if canonical_sha256(canonical_payload) != package_sha256:
            raise ValueError("legacy package hash does not match")
        expected_id = canonical_sha256(
            {
                "protocol_version": "full-persona-package/0.2",
                "pack_sha256": pack_sha256,
                "dossier_sha256": _nested_digest(payload, "dossier", "dossier_sha256"),
                "evolution_sha256": _nested_digest(payload, "evolution", "evolution_sha256"),
            }
        )
        if package_id != expected_id:
            raise ValueError("legacy package identifier does not match")
        _require_pointer_hash(package_sha256, expected)
        pack = self.pack_store.read_pack(run_id, pack_id)
        synthetic = payload.get("synthetic")
        if (
            pack.pack_sha256 != pack_sha256
            or not isinstance(synthetic, bool)
            or synthetic != self.synthetic
        ):
            raise ValueError("legacy package source binding does not match")
        return _inspection("full-persona-package/0.2", package_id, package_sha256)

    def _validate(self, package: FullPersonaPackage) -> None:
        try:
            checked = FullPersonaPackage.model_validate(package.model_dump(mode="json"))
        except (AttributeError, ValidationError) as exc:
            raise DataValidationError(
                "persona_package_invalid", "The private persona package is invalid."
            ) from exc
        if checked.synthetic != self.synthetic or checked.expires_at <= utc_now():
            _store_error("persona package mode or retention is invalid")
        pack = self.pack_store.read_pack(checked.source_run_id, checked.pack_id)
        if pack.pack_sha256 != checked.pack_sha256:
            _store_error("persona package source pack does not match")

    def _selected(self, run_id: str, package_id: str | None) -> tuple[str, str | None]:
        validate_digest(run_id)
        if package_id is not None:
            validate_digest(package_id)
            return package_id, None
        try:
            raw = _read_bounded(self._pointer(run_id), _MAX_POINTER_BYTES)
            pointer = json.loads(raw)
            selected = pointer["package_id"]
            digest = pointer["package_sha256"]
            if not isinstance(selected, str) or not isinstance(digest, str):
                raise ValueError
            validate_digest(selected)
            validate_digest(digest)
            return selected, digest
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise DataValidationError(
                "persona_package_pointer_invalid", "The persona package pointer is invalid."
            ) from exc

    def _read_path(self, path: Path) -> FullPersonaPackage:
        try:
            return FullPersonaPackage.model_validate_json(_read_bounded(path, _MAX_PACKAGE_BYTES))
        except (OSError, ValidationError, ValueError) as exc:
            raise DataValidationError(
                "persona_package_invalid", "The private persona package is invalid."
            ) from exc

    def _path(self, run_id: str, package_id: str) -> Path:
        validate_digest(run_id)
        validate_digest(package_id)
        return self._safe(self.pack_store.run_path(run_id) / f"{package_id}.persona-package.json")

    def _pointer(self, run_id: str) -> Path:
        validate_digest(run_id)
        return self._safe(self.pack_store.run_path(run_id) / "latest-persona-package.json")

    def _safe(self, path: Path) -> Path:
        root = self.pack_store.packs
        reject_link_if_present(root)
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise DataValidationError(
                "persona_package_path_escape", "A persona package escaped private storage."
            ) from exc
        current = root
        for part in relative.parts:
            current /= part
            reject_link_if_present(current)
        return path


def _inspection(
    protocol: PersonaPackageProtocol, package_id: str, package_sha256: str
) -> PersonaPackageInspection:
    current = protocol == "full-persona-package/0.3"
    return PersonaPackageInspection(
        protocol_version=protocol,
        package_id=package_id,
        package_sha256=package_sha256,
        adjudication_status="present" if current else "absent",
        review_eligible=current,
    )


def _digest_field(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError(f"persona package {field} is not a digest")
    validate_digest(value)
    return value


def _nested_digest(payload: dict[str, object], parent: str, field: str) -> str:
    nested = payload.get(parent)
    if not isinstance(nested, dict):
        raise ValueError(f"persona package {parent} is invalid")
    return _digest_field(nested, field)


def _require_pointer_hash(package_sha256: str, expected: str | None) -> None:
    if expected is not None and package_sha256 != expected:
        raise ValueError("persona package pointer is stale")


def _read_bounded(path: Path, limit: int) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        _store_error("persona package artifact exceeded its byte limit")
    return content


def _store_error(reason: str) -> None:
    raise DataValidationError(
        "persona_package_store_invalid",
        "The private persona package failed closed.",
        details={"reason": reason},
    )
