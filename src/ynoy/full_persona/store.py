from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.store_contract import (
    initial_head,
    model_bytes,
    pointer_bytes,
    validate_commit_payload,
    validate_digest,
    validate_next_head,
)
from ynoy.models.full_persona import (
    FullCorpusFileReceipt,
    FullCorpusHead,
    FullCorpusManifest,
    FullCorpusShardReceipt,
)
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.persona_study.transactions import exclusive_study_lock, exclusive_write_bytes
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes

_CONTROL_BYTES = 16 * 1024**2


class FullPersonaStore:
    """Private immutable shard store with one small mutable head pointer."""

    def __init__(self, root: Path, *, synthetic: bool):
        assessment = require_private_root(root, real_data=not synthetic)
        self.root = assessment.root
        self.synthetic = synthetic
        self.runs = self.root / "full-persona-runs"
        self.locks = self.root / "full-persona-locks"
        self.staging = self.root / "full-persona-staging"
        for path in (self.runs, self.locks, self.staging):
            reject_link_if_present(path)

    def write_manifest(self, manifest: FullCorpusManifest) -> FullCorpusHead:
        safe = self._validate_manifest(manifest)
        run = self._run(safe.run_id)
        if run.exists():
            existing = self.read_manifest(safe.run_id)
            if existing.manifest_sha256 != safe.manifest_sha256:
                raise DataValidationError(
                    "full_persona_run_collision", "A different manifest owns this run identifier."
                )
            return self.read_head(safe.run_id)
        run.mkdir(parents=True, exist_ok=False)
        for name in ("heads", "shards", "files"):
            (run / name).mkdir()
        exclusive_write_bytes(run / "manifest.json", model_bytes(safe))
        head = initial_head(safe)
        exclusive_write_bytes(self._head_path(safe.run_id, 0), model_bytes(head))
        atomic_write_bytes(run / "head.json", pointer_bytes(head))
        return head

    def read_manifest(self, run_id: str) -> FullCorpusManifest:
        try:
            value = FullCorpusManifest.model_validate_json(
                _read_bounded(self._run(run_id) / "manifest.json")
            )
        except (ValidationError, OSError) as exc:
            raise DataValidationError(
                "full_persona_manifest_invalid", "The private full-persona manifest is invalid."
            ) from exc
        return self._validate_manifest(value)

    def read_head(self, run_id: str) -> FullCorpusHead:
        run = self._run(run_id)
        try:
            pointer = json.loads(_read_bounded(run / "head.json"))
            revision = pointer["revision"]
            expected = pointer["head_sha256"]
            if not isinstance(revision, int) or not isinstance(expected, str):
                raise ValueError
            head = FullCorpusHead.model_validate_json(
                _read_bounded(self._head_path(run_id, revision))
            )
        except (KeyError, TypeError, ValueError, ValidationError, OSError) as exc:
            raise DataValidationError(
                "full_persona_head_invalid", "The private full-persona head is invalid."
            ) from exc
        if head.head_sha256 != expected or head.run_id != run_id:
            raise DataValidationError(
                "full_persona_head_binding_invalid", "The full-persona head pointer is invalid."
            )
        return head

    def new_staging_path(self, run_id: str) -> Path:
        run = self._safe(self.staging / run_id)
        run.mkdir(parents=True, exist_ok=True)
        reject_link_if_present(run)
        return self._safe(run / f"{uuid4().hex}.jsonl.gz.tmp")

    def commit_revision(
        self,
        expected: FullCorpusHead,
        head: FullCorpusHead,
        *,
        staging_shard: Path | None = None,
        shard_receipt: FullCorpusShardReceipt | None = None,
        file_receipts: tuple[FullCorpusFileReceipt, ...] = (),
    ) -> FullCorpusHead:
        current = self.read_head(expected.run_id)
        if current.head_sha256 != expected.head_sha256:
            raise DataValidationError(
                "full_persona_stale_head", "The full-persona head advanced concurrently."
            )
        validate_next_head(current, head)
        manifest = self.read_manifest(head.run_id)
        validate_commit_payload(head, staging_shard, shard_receipt, file_receipts)
        if head.output_bytes > manifest.limits.max_run_output_bytes:
            raise DataValidationError(
                "full_persona_output_quota", "The full-persona run exceeded its output quota."
            )
        if staging_shard is not None and shard_receipt is not None:
            self._commit_shard(head.run_id, staging_shard, shard_receipt)
        for receipt in file_receipts:
            self._write_file_receipt(head.run_id, receipt)
        exclusive_write_bytes(self._head_path(head.run_id, head.revision), model_bytes(head))
        atomic_write_bytes(self._run(head.run_id) / "head.json", pointer_bytes(head))
        return head

    def lock(self, run_id: str) -> AbstractContextManager[None]:
        return exclusive_study_lock(self._safe(self.locks / f"{run_id}.lock"))

    def iter_shard_paths(self, run_id: str) -> Iterator[Path]:
        root = self._safe(self._run(run_id) / "shards")
        reject_link_if_present(root)
        for path in sorted(root.glob("*.jsonl.gz")):
            require_regular_file(path)
            yield path

    def discard_staging(self, path: Path) -> None:
        safe = self._safe(path)
        if safe.exists():
            require_regular_file(safe)
            safe.unlink()

    def run_path(self, run_id: str) -> Path:
        return self._run(run_id)

    def staging_run_path(self, run_id: str) -> Path:
        return self._safe(self.staging / run_id)

    def _commit_shard(self, run_id: str, staging: Path, receipt: FullCorpusShardReceipt) -> None:
        safe = self._safe(staging)
        require_regular_file(safe)
        if safe.stat().st_size != receipt.compressed_bytes:
            raise DataValidationError(
                "full_persona_shard_size_mismatch", "A staged shard has the wrong size."
            )
        destination = self._safe(self._run(run_id) / receipt.relative_path)
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            raise DataValidationError(
                "full_persona_shard_exists", "Refusing to overwrite an immutable shard."
            )
        os.replace(safe, destination)
        exclusive_write_bytes(destination.with_suffix(".receipt.json"), model_bytes(receipt))

    def _write_file_receipt(self, run_id: str, receipt: FullCorpusFileReceipt) -> None:
        path = self._safe(self._run(run_id) / "files" / f"{receipt.file_index:08d}.json")
        exclusive_write_bytes(path, model_bytes(receipt))

    def _head_path(self, run_id: str, revision: int) -> Path:
        return self._safe(self._run(run_id) / "heads" / f"{revision:08d}.json")

    def _run(self, run_id: str) -> Path:
        validate_digest(run_id)
        return self._safe(self.runs / run_id)

    def _safe(self, candidate: Path) -> Path:
        reject_link_if_present(self.root)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise DataValidationError(
                "full_persona_path_escape", "A full-persona artifact escaped its private root."
            ) from exc
        current = self.root
        for part in candidate.relative_to(self.root).parts:
            current /= part
            reject_link_if_present(current)
        return candidate

    def _validate_manifest(self, manifest: FullCorpusManifest) -> FullCorpusManifest:
        try:
            safe = FullCorpusManifest.model_validate(manifest.model_dump(mode="python"))
        except ValidationError as exc:
            raise DataValidationError(
                "full_persona_manifest_invalid", "The full-persona manifest is invalid."
            ) from exc
        if safe.synthetic != self.synthetic:
            raise DataValidationError(
                "full_persona_mode_mismatch", "The full-persona storage mode does not match."
            )
        return safe


def _read_bounded(path: Path) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        value = stream.read(_CONTROL_BYTES + 1)
    if len(value) > _CONTROL_BYTES:
        raise DataValidationError(
            "full_persona_control_oversized", "A full-persona control artifact is oversized."
        )
    return value
