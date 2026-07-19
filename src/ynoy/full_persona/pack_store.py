from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import model_bytes, validate_digest
from ynoy.models.full_persona_pack import PersonaPack, PersonaPackReceipt
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes, canonical_sha256, utc_now

_MAX_PACK_BYTES = 32 * 1024**2
_CONTROL_BYTES = 1024**2


class FullPersonaPackStore:
    """Private immutable packs with a small latest-pack pointer per source run."""

    def __init__(self, root: Path, *, synthetic: bool):
        assessment = require_private_root(root, real_data=not synthetic)
        self.root = assessment.root
        self.synthetic = synthetic
        self.packs = self.root / "full-persona-packs"
        reject_link_if_present(self.packs)

    def write_pack(self, pack: PersonaPack) -> PersonaPackReceipt:
        self._validate_mode(pack)
        encoded = model_bytes(pack)
        if len(encoded) > _MAX_PACK_BYTES:
            raise DataValidationError(
                "persona_pack_oversized", "The bounded persona pack exceeded its storage limit."
            )
        source = FullPersonaStore(self.root, synthetic=self.synthetic)
        with source.lock(pack.source_run_id):
            self._validate_source(pack, source)
            return self._write_locked(pack, encoded)

    def _write_locked(self, pack: PersonaPack, encoded: bytes) -> PersonaPackReceipt:
        run = self._run(pack.source_run_id)
        run.mkdir(parents=True, exist_ok=True)
        path = self._pack_path(pack.source_run_id, pack.pack_id)
        receipt = _receipt(pack)
        if path.exists():
            existing = self._read_pack_path(path)
            if existing.pack_sha256 != pack.pack_sha256:
                raise DataValidationError(
                    "persona_pack_collision", "A different pack owns this identifier."
                )
        else:
            _write_immutable(path, encoded)
            _write_immutable(self._receipt_path(path), model_bytes(receipt))
        atomic_write_bytes(
            run / "latest.json",
            canonical_json_bytes({"pack_id": pack.pack_id, "pack_sha256": pack.pack_sha256}),
        )
        return receipt

    def read_pack(self, run_id: str, pack_id: str | None = None) -> PersonaPack:
        source = FullPersonaStore(self.root, synthetic=self.synthetic)
        with source.lock(run_id):
            return self._read_locked(run_id, pack_id, source)

    def _read_locked(
        self,
        run_id: str,
        pack_id: str | None,
        source: FullPersonaStore,
    ) -> PersonaPack:
        selected, expected_sha = self._selected_pack(run_id, pack_id)
        pack = self._read_pack_path(self._pack_path(run_id, selected))
        self._validate_mode(pack)
        if pack.source_run_id != run_id or (expected_sha and pack.pack_sha256 != expected_sha):
            _store_error("pack pointer is not bound to its immutable artifact")
        receipt = self._read_receipt(self._receipt_path(self._pack_path(run_id, selected)))
        if (
            receipt.pack_id != pack.pack_id
            or receipt.source_run_id != run_id
            or receipt.source_head_sha256 != pack.source_head_sha256
            or receipt.pack_sha256 != pack.pack_sha256
        ):
            _store_error("pack receipt does not bind its immutable artifact")
        self._validate_source(pack, source)
        return pack

    def run_path(self, run_id: str) -> Path:
        return self._run(run_id)

    def _selected_pack(self, run_id: str, pack_id: str | None) -> tuple[str, str | None]:
        validate_digest(run_id)
        if pack_id is not None:
            validate_digest(pack_id)
            return pack_id, None
        try:
            pointer = json.loads(_read_bounded(self._run(run_id) / "latest.json", _CONTROL_BYTES))
            selected = pointer["pack_id"]
            digest = pointer["pack_sha256"]
            if not isinstance(selected, str) or not isinstance(digest, str):
                raise ValueError
            validate_digest(selected)
            validate_digest(digest)
            return selected, digest
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise DataValidationError(
                "persona_pack_pointer_invalid", "The private persona pack pointer is invalid."
            ) from exc

    def _read_pack_path(self, path: Path) -> PersonaPack:
        try:
            return PersonaPack.model_validate_json(_read_bounded(path, _MAX_PACK_BYTES))
        except (OSError, ValidationError, ValueError) as exc:
            raise DataValidationError(
                "persona_pack_invalid", "The private persona pack is invalid."
            ) from exc

    def _read_receipt(self, path: Path) -> PersonaPackReceipt:
        try:
            return PersonaPackReceipt.model_validate_json(_read_bounded(path, _CONTROL_BYTES))
        except (OSError, ValidationError, ValueError) as exc:
            raise DataValidationError(
                "persona_pack_receipt_invalid", "The private persona pack receipt is invalid."
            ) from exc

    def _validate_mode(self, pack: PersonaPack) -> None:
        if pack.synthetic != self.synthetic:
            raise DataValidationError(
                "persona_pack_mode_mismatch", "The persona pack storage mode does not match."
            )

    def _validate_source(self, pack: PersonaPack, source: FullPersonaStore) -> None:
        manifest = source.read_manifest(pack.source_run_id)
        head = source.read_head(pack.source_run_id)
        if manifest.expires_at <= utc_now() or pack.expires_at != manifest.expires_at:
            _store_error("pack or source retention has expired")
        if (
            head.status != "complete"
            or head.head_sha256 != pack.source_head_sha256
            or manifest.manifest_sha256 != pack.source_manifest_sha256
        ):
            _store_error("pack source head is stale or invalid")
        verify_committed_run(source, manifest, head)

    def _run(self, run_id: str) -> Path:
        validate_digest(run_id)
        return self._safe(self.packs / run_id)

    def _pack_path(self, run_id: str, pack_id: str) -> Path:
        validate_digest(pack_id)
        return self._safe(self._run(run_id) / f"{pack_id}.json")

    def _receipt_path(self, pack_path: Path) -> Path:
        return self._safe(pack_path.with_suffix(".receipt.json"))

    def _safe(self, candidate: Path) -> Path:
        reject_link_if_present(self.root)
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as exc:
            raise DataValidationError(
                "persona_pack_path_escape", "A persona pack escaped its private root."
            ) from exc
        current = self.root
        for part in relative.parts:
            current /= part
            reject_link_if_present(current)
        return candidate


def _receipt(pack: PersonaPack) -> PersonaPackReceipt:
    payload = {
        "pack_id": pack.pack_id,
        "source_run_id": pack.source_run_id,
        "source_head_sha256": pack.source_head_sha256,
        "pack_sha256": pack.pack_sha256,
        "relative_path": f"{pack.source_run_id}/{pack.pack_id}.json",
    }
    draft = cast(Any, PersonaPackReceipt).model_construct(**payload, receipt_sha256="0" * 64)
    return PersonaPackReceipt.model_validate(
        {
            **payload,
            "receipt_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"receipt_sha256"})
            ),
        }
    )


def _read_bounded(path: Path, limit: int) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        _store_error("a persona pack artifact exceeded its byte limit")
    return value


def _write_immutable(path: Path, content: bytes) -> None:
    if path.exists():
        _store_error("refusing to overwrite an immutable persona pack artifact")
    atomic_write_bytes(path, content)


def _store_error(reason: str) -> None:
    raise DataValidationError(
        "persona_pack_store_invalid",
        "The private persona pack failed closed.",
        details={"reason": reason},
    )
