from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from ynoy.errors import DataValidationError, StorageError
from ynoy.full_persona.run_lock import exclusive_run_lock
from ynoy.persona_study.storage_paths import reject_link_if_present

from . import read_support
from .contracts import DocumentRef, NodeRead, PageRead, PreparedDocument
from .json_codec import canonical_json_bytes
from .normalization import normalize_document
from .plane_storage import (
    assert_document_capacity_locked,
    check_index_root,
    ensure_index_root,
    index_integrity_error,
    list_documents_locked,
    prepare_index_lock_file,
    publish_verified_document,
    read_document_path,
    resolve_index_plane,
)

_DOCUMENT_ID = re.compile(r"^[0-9a-f]{64}$")


class StructuralIndex:
    """Private, immutable, deterministic index for prepared documents."""

    def __init__(self, root: Path, *, synthetic: bool = False) -> None:
        self.root, self._data_plane = resolve_index_plane(root, synthetic)
        reject_link_if_present(self.root)

    def import_document(self, bundle: PreparedDocument) -> DocumentRef:
        """Persist one validated prepared document, idempotently by stable content ID."""
        payload = normalize_document(bundle, data_plane=self._data_plane)
        encoded = canonical_json_bytes(payload)
        ensure_index_root(self.root)
        try:
            prepare_index_lock_file(self.root)
            with exclusive_run_lock(self.root / "index.lock", expose_handle=True) as lock_handle:
                path = self.root / f"{payload['document_id']}.json"
                reject_link_if_present(path)
                if path.exists():
                    existing = read_document_path(
                        path,
                        private_root=self.root,
                        expected_data_plane=self._data_plane,
                    )
                    if canonical_json_bytes(existing) != encoded:
                        raise index_integrity_error("immutable document ID collision")
                    return read_support.document_ref(existing)
                assert_document_capacity_locked(self.root, lock_handle)
                publish_verified_document(
                    path,
                    encoded,
                    private_root=self.root,
                    expected_data_plane=self._data_plane,
                )
        except DataValidationError:
            raise
        except OSError as exc:
            raise StorageError(
                "structural_index_storage_failed", "Structural index could not be written."
            ) from exc
        return read_support.document_ref(payload)

    def list_documents(self) -> list[DocumentRef]:
        """Return verified documents in stable ID order."""
        check_index_root(self.root)
        if not self.root.exists():
            return []
        try:
            prepare_index_lock_file(self.root)
            with exclusive_run_lock(self.root / "index.lock", expose_handle=True) as handle:
                return list_documents_locked(self.root, handle, self._data_plane)
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

    def _load_document(self, document_id: str) -> dict[str, object]:
        if not isinstance(document_id, str) or not _DOCUMENT_ID.fullmatch(document_id):
            raise DataValidationError(
                "structural_index_input_invalid", "Document ID must be a stable SHA-256 ID."
            )
        check_index_root(self.root)
        path = self.root / f"{document_id}.json"
        reject_link_if_present(path)
        if not path.exists():
            raise DataValidationError(
                "structural_index_document_not_found", "Structural document was not found."
            )
        try:
            payload = read_document_path(
                path, private_root=self.root, expected_data_plane=self._data_plane
            )
        except OSError as exc:
            raise StorageError(
                "structural_index_storage_failed", "Structural document could not be read."
            ) from exc
        if payload["document_id"] != document_id:
            raise index_integrity_error("document ID does not match its immutable path")
        return payload
