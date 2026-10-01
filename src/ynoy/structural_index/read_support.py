from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from ynoy.errors import DataValidationError

from .contracts import DocumentRef, PageRead

MAX_NODE_PAGE_RESULTS = 50_000
_MAX_PAGE_READS = 10_000
_MAX_NODE_READS = 256


def document_ref(payload: dict[str, object]) -> DocumentRef:
    return DocumentRef(
        document_id=cast(str, payload["document_id"]),
        name=cast(str, payload["name"]),
        description=cast(str | None, payload["description"]),
        page_count=cast(int, payload["page_count"]),
        content_sha256=cast(str, payload["content_sha256"]),
    )


def page_read(payload: dict[str, object], number: int) -> PageRead:
    pages = cast(list[dict[str, object]], payload["pages"])
    page = pages[number - 1]
    return PageRead(
        document_id=cast(str, payload["document_id"]),
        page_number=number,
        source_ref=cast(str, page["source_ref"]),
        content_sha256=cast(str, page["content_sha256"]),
        text=cast(str, page["text"]),
    )


def validate_page_numbers(numbers: object, page_count: int) -> list[int]:
    if isinstance(numbers, (str, bytes, bytearray)) or not isinstance(numbers, Sequence):
        raise DataValidationError(
            "structural_index_input_invalid", "Page numbers must be a finite sequence."
        )
    if len(numbers) > _MAX_PAGE_READS:
        raise DataValidationError(
            "structural_index_read_limit", "Page read exceeds the page-count limit."
        )
    result: list[int] = []
    seen: set[int] = set()
    for number in numbers:
        if type(number) is not int or not 1 <= number <= page_count:
            raise DataValidationError(
                "structural_index_input_invalid", "Page number is outside the document."
            )
        if number in seen:
            raise DataValidationError(
                "structural_index_page_ref_duplicate", "Duplicate page references are invalid."
            )
        seen.add(number)
        result.append(number)
    return result


def validate_node_ids(node_ids: object) -> list[str]:
    if isinstance(node_ids, (str, bytes, bytearray)) or not isinstance(node_ids, Sequence):
        raise DataValidationError(
            "structural_index_input_invalid", "Node IDs must be a finite sequence."
        )
    if len(node_ids) > _MAX_NODE_READS:
        raise DataValidationError(
            "structural_index_read_limit", "Node read exceeds the selection limit."
        )
    result: list[str] = []
    seen: set[str] = set()
    for node_id in node_ids:
        if not isinstance(node_id, str) or not node_id:
            raise DataValidationError(
                "structural_index_input_invalid", "Node IDs must be non-empty strings."
            )
        if node_id in seen:
            raise DataValidationError(
                "structural_index_node_ref_duplicate", "Duplicate node references are invalid."
            )
        seen.add(node_id)
        result.append(node_id)
    return result


def index_nodes(roots: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    stack = list(reversed(roots))
    while stack:
        node = stack.pop()
        result[cast(str, node["node_id"])] = node
        children = node.get("nodes", [])
        if isinstance(children, list):
            stack.extend(reversed(cast(list[dict[str, object]], children)))
    return result
