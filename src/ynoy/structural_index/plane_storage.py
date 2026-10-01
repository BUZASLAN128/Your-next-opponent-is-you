from __future__ import annotations

import os
import re
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from ynoy.errors import DataValidationError
from ynoy.persona_study.storage_paths import reject_link_if_present
from ynoy.policy import require_private_root
from ynoy.private_files import (
    create_private_file,
    ensure_private_root,
    open_exclusive_private_utf8,
    validate_private_file,
)

from . import read_support
from .contracts import DocumentRef
from .json_codec import canonical_json_bytes, strict_json_object
from .normalization import DataPlaneName, verify_stored_document
from .validation import MAX_DOCUMENT_BYTES

_DOCUMENT_ID = re.compile(r"^[0-9a-f]{64}$")
_LOCK_MARKER = b"full-persona-os-lock/0.1"
_MAX_DOCUMENTS = 50_000


def resolve_index_plane(root: Path, synthetic: bool) -> tuple[Path, DataPlaneName]:
    assessment = require_private_root(root, real_data=not synthetic)
    if synthetic:
        return assessment.root / "structural-index-synthetic", "public_synthetic"
    return assessment.root / "structural-index", "private"


def index_integrity_error(reason: str) -> DataValidationError:
    return DataValidationError(
        "structural_index_integrity_invalid",
        "Stored structural index failed integrity validation.",
        details={"reason": reason},
    )


def check_index_root(root: Path) -> None:
    reject_link_if_present(root)
    if not root.exists():
        return
    if not root.is_dir():
        raise index_integrity_error("index root is not a directory")
    ensure_private_root(root)


def ensure_index_root(root: Path) -> None:
    check_index_root(root)
    ensure_private_root(root)
    check_index_root(root)


def prepare_index_lock_file(root: Path) -> None:
    path = root / "index.lock"
    try:
        create_private_file(path, private_root=root)
    except DataValidationError as exc:
        if exc.code != "private_file_exists":
            raise
        validate_private_file(path, private_root=root)


def verify_index_lock_file(root: Path, path: Path, handle: BinaryIO) -> None:
    validate_private_file(path, private_root=root)
    position = handle.tell()
    try:
        handle.seek(0, 2)
        if handle.tell() > 128:
            raise index_integrity_error("index lock file has an unexpected format")
        handle.seek(0)
        if handle.read(129) != _LOCK_MARKER:
            raise index_integrity_error("index lock file has an unexpected format")
    finally:
        handle.seek(position)


def read_document_path(
    path: Path, *, private_root: Path, expected_data_plane: DataPlaneName
) -> dict[str, object]:
    validate_private_file(path, private_root=private_root)
    with path.open("rb") as stream:
        content = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise index_integrity_error("stored document exceeds the storage size limit")
    try:
        return verify_stored_document(
            strict_json_object(content), expected_data_plane=expected_data_plane
        )
    except DataValidationError as exc:
        if exc.code == "structural_index_integrity_invalid":
            raise
        raise index_integrity_error("stored document failed schema validation") from exc


def publish_verified_document(
    path: Path,
    encoded: bytes,
    *,
    private_root: Path,
    expected_data_plane: DataPlaneName,
) -> None:
    stage = path.with_name(f".{path.stem}.{uuid4().hex}.tmp")
    stage_created = False
    try:
        stage_handle = open_exclusive_private_utf8(stage, private_root=private_root)
        stage_created = True
        with stage_handle as handle:
            handle.write(encoded.decode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        verified = read_document_path(
            stage, private_root=private_root, expected_data_plane=expected_data_plane
        )
        if canonical_json_bytes(verified) != encoded:
            raise index_integrity_error("prepared document failed reload verification")
        reject_link_if_present(path)
        if path.exists():
            raise index_integrity_error("immutable document appeared during publication")
        try:
            os.link(stage, path)
        except FileExistsError as exc:
            reject_link_if_present(path)
            raise index_integrity_error(
                "immutable document appeared during publication"
            ) from exc
    finally:
        if stage_created:
            stage.unlink(missing_ok=True)


def list_documents_locked(
    root: Path, lock_handle: BinaryIO, expected_data_plane: DataPlaneName
) -> list[DocumentRef]:
    check_index_root(root)
    entries: list[Path] = []
    for entry in root.iterdir():
        if entry.name == "index.lock":
            verify_index_lock_file(root, entry, lock_handle)
            continue
        if not _DOCUMENT_ID.fullmatch(entry.stem) or entry.suffix != ".json":
            raise index_integrity_error("index directory contains an unknown artifact")
        entries.append(entry)
        if len(entries) > _MAX_DOCUMENTS:
            raise index_integrity_error("index exceeds the document-count limit")
    result: list[DocumentRef] = []
    for path in sorted(entries, key=lambda item: item.stem):
        payload = read_document_path(
            path, private_root=root, expected_data_plane=expected_data_plane
        )
        if payload["document_id"] != path.stem:
            raise index_integrity_error("document ID does not match its immutable path")
        result.append(read_support.document_ref(payload))
    return result


def assert_document_capacity_locked(root: Path, lock_handle: BinaryIO) -> None:
    """Refuse another immutable document while holding the index OS lock."""
    document_count = 0
    for entry in root.iterdir():
        if entry.name == "index.lock":
            verify_index_lock_file(root, entry, lock_handle)
            continue
        if not _DOCUMENT_ID.fullmatch(entry.stem) or entry.suffix != ".json":
            raise index_integrity_error("index directory contains an unknown artifact")
        document_count += 1
        if document_count > _MAX_DOCUMENTS:
            raise index_integrity_error("index exceeds the document-count limit")
    if document_count >= _MAX_DOCUMENTS:
        raise DataValidationError(
            "structural_index_document_limit",
            "Structural index has reached its document-count limit.",
        )
