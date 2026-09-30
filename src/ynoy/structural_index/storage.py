from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO, cast
from uuid import uuid4

from ynoy.errors import DataValidationError, StorageError
from ynoy.full_persona.run_lock import exclusive_run_lock
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes

from . import read_support
from .contracts import DocumentRef, NodeRead, PageRead, PreparedDocument
from .json_codec import canonical_json_bytes, strict_json_object
from .normalization import normalize_document, verify_stored_document
from .validation import MAX_DOCUMENT_BYTES

_DOCUMENT_ID = re.compile(r"^[0-9a-f]{64}$")
_LOCK_MARKER = b"full-persona-os-lock/0.1"
_MAX_DOCUMENTS = 50_000


class StructuralIndex:
    """Private, immutable, deterministic index for prepared documents."""

    def __init__(self, root: Path, *, synthetic: bool = False) -> None:
        assessment = require_private_root(root, real_data=not synthetic)
        self.root = assessment.root / "structural-index"
        reject_link_if_present(self.root)

    def import_document(self, bundle: PreparedDocument) -> DocumentRef:
        """Persist one validated prepared document, idempotently by stable content ID."""
        payload = normalize_document(bundle)
        encoded = canonical_json_bytes(payload)
        self._ensure_root()
        try:
            with exclusive_run_lock(self.root / "index.lock"):
                path = self.root / f"{payload['document_id']}.json"
                reject_link_if_present(path)
                if path.exists():
                    existing = self._read_path(path)
                    if canonical_json_bytes(existing) != encoded:
                        raise self._integrity_error("immutable document ID collision")
                    return read_support.document_ref(existing)
                self._publish_verified(path, encoded)
        except DataValidationError:
            raise
        except OSError as exc:
            raise StorageError(
                "structural_index_storage_failed", "Structural index could not be written."
            ) from exc
        return read_support.document_ref(payload)

    def list_documents(self) -> list[DocumentRef]:
        """Return verified documents in stable ID order."""
        self._check_root()
        if not self.root.exists():
            return []
        try:
            with exclusive_run_lock(self.root / "index.lock", expose_handle=True) as handle:
                return self._list_documents_locked(handle)
        except DataValidationError:
            raise
        except OSError as exc:
            raise StorageError(
                "structural_index_storage_failed", "Structural index could not be read."
            ) from exc

    def read_tree(self, document_id: str) -> dict[str, object] | list[dict[str, object]]:
        """Return the validated PageIndex-compatible tree with its input root shape."""
        payload = self._load_document(document_id)
        roots = cast(list[dict[str, object]], payload["tree"])
        if payload["tree_shape"] == "object":
            return roots[0]
        return roots

    def read_pages(self, document_id: str, page_numbers: Sequence[int]) -> list[PageRead]:
        """Read exact, hash-bound page text in caller order; duplicate refs are rejected."""
        payload = self._load_document(document_id)
        numbers = read_support.validate_page_numbers(
            page_numbers, cast(int, payload["page_count"])
        )
        return [read_support.page_read(payload, number) for number in numbers]

    def read_nodes(self, document_id: str, node_ids: Sequence[str]) -> list[NodeRead]:
        """Read selected nodes with exact pages from every inclusive source span."""
        payload = self._load_document(document_id)
        requested = read_support.validate_node_ids(node_ids)
        nodes = read_support.index_nodes(cast(list[dict[str, object]], payload["tree"]))
        missing = [node_id for node_id in requested if node_id not in nodes]
        if missing:
            raise DataValidationError(
                "structural_index_node_not_found", "A requested structural node was not found."
            )
        result: list[NodeRead] = []
        total_pages = 0
        for node_id in requested:
            node = nodes[node_id]
            start = cast(int, node["start_index"])
            end = cast(int, node["end_index"])
            total_pages += end - start + 1
            if total_pages > read_support.MAX_NODE_PAGE_RESULTS:
                raise DataValidationError(
                    "structural_index_read_limit", "Requested nodes exceed the page-read limit."
                )
            pages = tuple(
                read_support.page_read(payload, number) for number in range(start, end + 1)
            )
            summary = cast(str | None, node.get("summary"))
            result.append(
                NodeRead(
                    document_id=document_id,
                    node_id=node_id,
                    title=cast(str, node["title"]),
                    start_index=start,
                    end_index=end,
                    summary=summary,
                    pages=pages,
                )
            )
        return result

    def _list_documents_locked(self, lock_handle: BinaryIO) -> list[DocumentRef]:
        self._check_root()
        entries: list[Path] = []
        for entry in self.root.iterdir():
            if entry.name == "index.lock":
                self._verify_lock_file(entry, lock_handle)
                continue
            if not _DOCUMENT_ID.fullmatch(entry.stem) or entry.suffix != ".json":
                raise self._integrity_error("index directory contains an unknown artifact")
            entries.append(entry)
            if len(entries) > _MAX_DOCUMENTS:
                raise self._integrity_error("index exceeds the document-count limit")
        result: list[DocumentRef] = []
        for path in sorted(entries, key=lambda item: item.stem):
            payload = self._read_path(path)
            if payload["document_id"] != path.stem:
                raise self._integrity_error("document ID does not match its immutable path")
            result.append(read_support.document_ref(payload))
        return result

    def _load_document(self, document_id: str) -> dict[str, object]:
        if not isinstance(document_id, str) or not _DOCUMENT_ID.fullmatch(document_id):
            raise DataValidationError(
                "structural_index_input_invalid", "Document ID must be a stable SHA-256 ID."
            )
        self._check_root()
        path = self.root / f"{document_id}.json"
        reject_link_if_present(path)
        if not path.exists():
            raise DataValidationError(
                "structural_index_document_not_found", "Structural document was not found."
            )
        try:
            payload = self._read_path(path)
        except OSError as exc:
            raise StorageError(
                "structural_index_storage_failed", "Structural document could not be read."
            ) from exc
        if payload["document_id"] != document_id:
            raise self._integrity_error("document ID does not match its immutable path")
        return payload

    def _read_path(self, path: Path) -> dict[str, object]:
        require_regular_file(path)
        with path.open("rb") as stream:
            content = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise self._integrity_error("stored document exceeds the storage size limit")
        try:
            return verify_stored_document(strict_json_object(content))
        except DataValidationError as exc:
            if exc.code == "structural_index_integrity_invalid":
                raise
            raise self._integrity_error("stored document failed schema validation") from exc

    def _publish_verified(self, path: Path, encoded: bytes) -> None:
        stage = path.with_name(f".{path.stem}.{uuid4().hex}.tmp")
        try:
            atomic_write_bytes(stage, encoded)
            verified = self._read_path(stage)
            if canonical_json_bytes(verified) != encoded:
                raise self._integrity_error("prepared document failed reload verification")
            reject_link_if_present(path)
            if path.exists():
                raise self._integrity_error("immutable document appeared during publication")
            os.replace(stage, path)
        finally:
            stage.unlink(missing_ok=True)

    def _ensure_root(self) -> None:
        self._check_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._check_root()

    def _check_root(self) -> None:
        reject_link_if_present(self.root)
        if self.root.exists() and not self.root.is_dir():
            raise self._integrity_error("index root is not a directory")

    def _verify_lock_file(self, path: Path, handle: BinaryIO) -> None:
        require_regular_file(path)
        position = handle.tell()
        try:
            handle.seek(0, 2)
            if handle.tell() > 128:
                raise self._integrity_error("index lock file has an unexpected format")
            handle.seek(0)
            if handle.read(129) != _LOCK_MARKER:
                raise self._integrity_error("index lock file has an unexpected format")
        finally:
            handle.seek(position)

    @staticmethod
    def _integrity_error(reason: str) -> DataValidationError:
        return DataValidationError(
            "structural_index_integrity_invalid",
            "Stored structural index failed integrity validation.",
            details={"reason": reason},
        )
