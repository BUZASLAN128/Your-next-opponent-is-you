from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from ynoy.constants import CODEX_VAULT_BUFFER_BYTES
from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.models import CodexCorpusApproval, CodexMetadataInventory, CodexSnapshotReceipt
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes, sha256_file

_MAX_CONTROL_BYTES = 256 * 1024**2


class RawVaultStore:
    def __init__(self, root: Path, *, synthetic: bool):
        assessment = require_private_root(root, real_data=not synthetic)
        self.root = assessment.root
        self.vault = self.root / "raw-vault"

    def read_manifest(self, manifest_id: UUID) -> CodexMetadataInventory:
        path = self.root / "codex-metadata-inventory" / f"{manifest_id}.json"
        return _read_model(path, self.root, CodexMetadataInventory, "codex_manifest")

    def write_approval(self, approval: CodexCorpusApproval) -> Path:
        path = self.root / "codex-corpus-approvals" / f"{approval.record_id}.json"
        return _write_model(path, self.root, approval)

    def read_approval(self, approval_id: UUID) -> CodexCorpusApproval:
        path = self.root / "codex-corpus-approvals" / f"{approval_id}.json"
        return _read_model(path, self.root, CodexCorpusApproval, "codex_approval")

    def delete_approval(self, approval_id: UUID) -> None:
        path = self.root / "codex-corpus-approvals" / f"{approval_id}.json"
        safe = _safe_path(path, self.root, must_exist=False)
        if safe.exists():
            safe.unlink()

    def write_snapshot(self, receipt: CodexSnapshotReceipt) -> Path:
        receipt_path = self.vault / "snapshot-receipts" / f"{receipt.record_id}.json"
        _write_model(receipt_path, self.root, receipt)
        state_path = self.vault / "snapshots" / f"{receipt.snapshot_id}.json"
        return _write_model(state_path, self.root, receipt)

    def read_snapshot(self, snapshot_id: UUID) -> CodexSnapshotReceipt:
        path = self.vault / "snapshots" / f"{snapshot_id}.json"
        return _read_model(path, self.root, CodexSnapshotReceipt, "codex_snapshot")

    def vault_file(self, item: DiscoveredCodexFile) -> tuple[str, int]:
        staging = self.vault / "staging" / f"{uuid4().hex}.tmp"
        staging.parent.mkdir(parents=True, exist_ok=True)
        try:
            digest, count = _copy_stable_source(item, staging)
            if count != item.file_bytes:
                raise DataValidationError(
                    "codex_source_changed_during_snapshot",
                    "Codex source byte count changed during snapshot.",
                )
            destination = self.blob_path(digest)
            _install_verified_blob(staging, destination, digest, count)
            return digest, count
        finally:
            if staging.exists():
                staging.unlink()

    def blob_path(self, blob_sha256: str) -> Path:
        if len(blob_sha256) != 64 or any(char not in "0123456789abcdef" for char in blob_sha256):
            raise DataValidationError("blob_hash_invalid", "Raw-vault blob hash is invalid.")
        return self.vault / "blobs" / "sha256" / blob_sha256[:2] / blob_sha256

    @contextmanager
    def open_blob(self, blob_sha256: str, expected_bytes: int) -> Iterator[BinaryIO]:
        path = self.blob_path(blob_sha256)
        _verify_blob(path, blob_sha256, expected_bytes)
        with path.open("rb") as stream:
            yield stream


def _copy_stable_source(item: DiscoveredCodexFile, destination: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    with open_stable_codex_file(item) as source, destination.open("xb") as target:
        for chunk in iter(lambda: source.read(CODEX_VAULT_BUFFER_BYTES), b""):
            target.write(chunk)
            digest.update(chunk)
            count += len(chunk)
        target.flush()
        os.fsync(target.fileno())
    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    return digest.hexdigest(), count


def _install_verified_blob(staging: Path, destination: Path, digest: str, count: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        _verify_blob(destination, digest, count)
        return
    try:
        os.replace(staging, destination)
    except OSError as exc:
        raise DataValidationError(
            "raw_vault_install_failed", "Raw-vault blob could not be installed atomically."
        ) from exc


def _verify_blob(path: Path, digest: str, expected_bytes: int) -> None:
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise DataValidationError(
            "raw_vault_blob_missing", "Raw-vault blob is unavailable."
        ) from exc
    if path.is_symlink() or path.is_junction() or not resolved.is_file():
        raise DataValidationError(
            "raw_vault_blob_invalid", "Raw-vault blob must be a regular file."
        )
    if metadata.st_size != expected_bytes:
        raise DataValidationError("raw_vault_blob_size_mismatch", "Raw-vault blob size changed.")
    if sha256_file(resolved, chunk_size=CODEX_VAULT_BUFFER_BYTES) != digest:
        raise DataValidationError("raw_vault_blob_hash_mismatch", "Raw-vault blob hash changed.")


def _write_model(path: Path, root: Path, model: BaseModel) -> Path:
    safe = _safe_path(path, root, must_exist=False)
    atomic_write_bytes(safe, canonical_json_bytes(model.model_dump(mode="json")))
    return safe


def _read_model[ModelT: BaseModel](
    path: Path, root: Path, model: type[ModelT], label: str
) -> ModelT:
    safe = _safe_path(path, root, must_exist=True)
    try:
        with safe.open("rb") as stream:
            payload = stream.read(_MAX_CONTROL_BYTES + 1)
        if len(payload) > _MAX_CONTROL_BYTES:
            raise ValueError("control artifact exceeds bound")
        return model.model_validate(json.loads(payload))
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise DataValidationError(
            f"{label}_invalid", f"Private {label.replace('_', ' ')} is unavailable or invalid."
        ) from exc


def _safe_path(path: Path, root: Path, *, must_exist: bool) -> Path:
    try:
        safe = path.resolve(strict=must_exist)
    except OSError as exc:
        raise DataValidationError(
            "private_artifact_unavailable", "Private artifact is unavailable."
        ) from exc
    if root != safe and root not in safe.parents:
        raise DataValidationError("artifact_path_escape", "Private artifact escaped its root.")
    return safe
