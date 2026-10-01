from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Literal, cast

from ynoy.errors import DataValidationError

from .contracts import PreparedDocument, TreeInput
from .json_codec import canonical_json_bytes
from .validation import (
    MAX_DESCRIPTION_BYTES,
    MAX_DOCUMENT_BYTES,
    MAX_PAGE_BYTES,
    MAX_PAGES,
    bounded_text,
    identity_node,
    input_error,
    integrity_error,
    normalize_tree,
    utf8_size,
    validate_scopes,
)

DataPlaneName = Literal["private", "public_synthetic"]


def normalize_document(
    bundle: PreparedDocument, *, data_plane: DataPlaneName
) -> dict[str, object]:
    if not isinstance(bundle, PreparedDocument):
        raise input_error("bundle must be a PreparedDocument")
    if data_plane not in ("private", "public_synthetic"):
        raise input_error("data plane is invalid")
    name = bounded_text(bundle.name, "name", 512, required=True)
    description = bounded_text(
        bundle.description, "description", MAX_DESCRIPTION_BYTES, required=False
    )
    pages = _normalize_pages(bundle.pages)
    roots, tree_shape = normalize_tree(bundle.tree, len(pages))
    identity_tree = [identity_node(node) for node in roots]
    identity = {
        "name": name,
        "description": description,
        "pages": pages,
        "tree_shape": tree_shape,
        "tree": identity_tree,
    }
    document_id = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()
    validate_scopes(roots, document_id, cast(str, name))
    roots = identity_tree
    content_sha256 = hashlib.sha256(canonical_json_bytes(pages)).hexdigest()
    page_records = [
        {
            "page_number": number,
            "source_ref": f"{document_id}#page={number}",
            "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text": text,
        }
        for number, text in enumerate(pages, start=1)
    ]
    payload: dict[str, object] = {
        "schema_version": "ynoy-structural-index/0.2",
        "data_plane": data_plane,
        "document_id": document_id,
        "name": name,
        "description": description,
        "page_count": len(pages),
        "content_sha256": content_sha256,
        "tree_shape": tree_shape,
        "tree": roots,
        "pages": page_records,
    }
    if len(canonical_json_bytes(payload)) > MAX_DOCUMENT_BYTES:
        raise input_error("prepared document exceeds the storage size limit")
    return payload


def verify_stored_document(
    value: object, *, expected_data_plane: DataPlaneName
) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise integrity_error("stored document must be an object")
    payload = cast(dict[str, object], value)
    expected_fields = {
        "schema_version",
        "data_plane",
        "document_id",
        "name",
        "description",
        "page_count",
        "content_sha256",
        "tree_shape",
        "tree",
        "pages",
    }
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != "ynoy-structural-index/0.2"
    ):
        raise integrity_error("stored schema is foreign or malformed")
    if payload.get("data_plane") != expected_data_plane:
        raise integrity_error("stored data plane does not match the selected index")
    pages = _stored_pages(payload.get("pages"))
    tree = payload.get("tree")
    shape = payload.get("tree_shape")
    if not isinstance(tree, list) or shape not in ("object", "array"):
        raise integrity_error("stored tree shape is invalid")
    if shape == "object" and len(tree) != 1:
        raise integrity_error("stored single-root tree has the wrong root count")
    try:
        prepared_tree: TreeInput = cast(TreeInput, tree[0] if shape == "object" else tree)
        prepared = PreparedDocument(
            name=cast(str, payload.get("name")),
            pages=pages,
            tree=prepared_tree,
            description=cast(str | None, payload.get("description")),
        )
        normalized = normalize_document(prepared, data_plane=expected_data_plane)
        stored = canonical_json_bytes(payload)
    except (DataValidationError, TypeError, ValueError) as exc:
        raise integrity_error("stored content failed schema validation") from exc
    if canonical_json_bytes(normalized) != stored:
        raise integrity_error("stored content failed canonical hash verification")
    return normalized


def _normalize_pages(pages: Sequence[str]) -> list[str]:
    if isinstance(pages, (str, bytes, bytearray)) or not isinstance(pages, Sequence):
        raise input_error("pages must be a finite sequence of strings")
    normalized: list[str] = []
    total_bytes = 0
    for page in pages:
        if len(normalized) >= MAX_PAGES:
            raise input_error("document exceeds the page-count limit")
        if not isinstance(page, str):
            raise input_error("each page must be exact source text")
        page_size = utf8_size(page, "page")
        if page_size > MAX_PAGE_BYTES:
            raise input_error("a source page exceeds the page-size limit")
        total_bytes += page_size
        if total_bytes > MAX_DOCUMENT_BYTES:
            raise input_error("prepared document exceeds the storage size limit")
        normalized.append(page)
    if not normalized:
        raise input_error("document must contain at least one page")
    return normalized


def _stored_pages(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > MAX_PAGES:
        raise integrity_error("stored page inventory is invalid")
    pages: list[str] = []
    for number, item in enumerate(value, start=1):
        if not isinstance(item, dict) or set(item) != {
            "page_number",
            "source_ref",
            "content_sha256",
            "text",
        }:
            raise integrity_error("stored page record has a foreign schema")
        text = item.get("text")
        if (
            not isinstance(text, str)
            or type(item.get("page_number")) is not int
            or item.get("page_number") != number
        ):
            raise integrity_error("stored page record has invalid types")
        pages.append(text)
    return tuple(pages)
