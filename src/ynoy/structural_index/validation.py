from __future__ import annotations

from collections.abc import Mapping, Sequence

from ynoy.errors import DataValidationError

MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
MAX_PAGES = 10_000
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_NODES = 50_000
MAX_DEPTH = 128
MAX_NAME_BYTES = 512
MAX_DESCRIPTION_BYTES = 4_096
MAX_TITLE_BYTES = 4_096
MAX_SUMMARY_BYTES = 16_384
_NODE_FIELDS = {
    "node_id",
    "title",
    "start_index",
    "end_index",
    "nodes",
    "summary",
    "document_id",
    "doc_id",
    "document_name",
    "document_scope",
}
_SCOPE_FIELDS = {"document_id", "doc_id", "document_name", "document_scope"}
# Validated scope declarations are removed before persistence.
MAX_NODE_JSON_FIELDS = len(_NODE_FIELDS) - len(_SCOPE_FIELDS)
MAX_PAGE_JSON_FIELDS = 4
MAX_ENVELOPE_JSON_FIELDS = 9
MAX_STORED_JSON_DEPTH = 2 * MAX_DEPTH + 1
MAX_STORED_JSON_VALUES = (
    MAX_NODES * (1 + MAX_NODE_JSON_FIELDS)
    + MAX_PAGES * (1 + MAX_PAGE_JSON_FIELDS)
    + MAX_ENVELOPE_JSON_FIELDS
    + 3
)


def normalize_tree(
    tree: object, page_count: int
) -> tuple[list[dict[str, object]], str]:
    if isinstance(tree, Mapping):
        raw_roots: Sequence[object] = (tree,)
        shape = "object"
    elif isinstance(tree, Sequence) and not isinstance(tree, (str, bytes, bytearray)):
        raw_roots = tree
        shape = "array"
    else:
        raise input_error("tree must be a node mapping or a sequence of node mappings")
    if not raw_roots or len(raw_roots) > MAX_NODES:
        raise input_error("tree root count is empty or exceeds the node limit")
    seen_ids: set[str] = set()
    active_objects: set[int] = set()
    node_count = [0]
    roots = [
        _normalize_node(node, page_count, seen_ids, active_objects, node_count, 1)
        for node in raw_roots
    ]
    return roots, shape


def _normalize_node(
    value: object,
    page_count: int,
    seen_ids: set[str],
    active_objects: set[int],
    node_count: list[int],
    depth: int,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise input_error("each tree node must be a mapping")
    identity = id(value)
    if identity in active_objects:
        raise input_error("tree contains a cycle")
    if depth > MAX_DEPTH:
        raise input_error("tree exceeds the nesting limit")
    active_objects.add(identity)
    try:
        node_count[0] += 1
        if node_count[0] > MAX_NODES:
            raise input_error("tree exceeds the node-count limit")
        if any(not isinstance(key, str) for key in value):
            raise input_error("tree node keys must be strings")
        if set(value) - _NODE_FIELDS:
            raise input_error("tree node contains an unsupported field")
        node_id = bounded_text(value.get("node_id"), "node_id", 256, required=True)
        assert node_id is not None
        if node_id in seen_ids:
            raise input_error("tree node identifiers must be unique")
        seen_ids.add(node_id)
        title = bounded_text(value.get("title"), "title", MAX_TITLE_BYTES, required=True)
        start = page_index(value.get("start_index"), page_count, "start_index")
        end = page_index(value.get("end_index"), page_count, "end_index")
        if end < start:
            raise input_error("node end_index must not precede start_index")
        node: dict[str, object] = {
            "node_id": node_id,
            "title": title,
            "start_index": start,
            "end_index": end,
        }
        _copy_optional_text_fields(value, node)
        if "nodes" in value:
            node["nodes"] = _normalize_children(
                value["nodes"], page_count, seen_ids, active_objects, node_count, depth
            )
        return node
    finally:
        active_objects.remove(identity)


def _normalize_children(
    value: object,
    page_count: int,
    seen_ids: set[str],
    active_objects: set[int],
    node_count: list[int],
    depth: int,
) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise input_error("nodes must be a sequence of child nodes")
    if len(value) + node_count[0] > MAX_NODES:
        raise input_error("tree exceeds the node-count limit")
    return [
        _normalize_node(child, page_count, seen_ids, active_objects, node_count, depth + 1)
        for child in value
    ]


def _copy_optional_text_fields(
    source: Mapping[str, object], target: dict[str, object]
) -> None:
    for field, maximum in (
        ("summary", MAX_SUMMARY_BYTES),
        ("document_id", 64),
        ("doc_id", 64),
        ("document_name", MAX_NAME_BYTES),
        ("document_scope", MAX_NAME_BYTES + 64),
    ):
        if field in source:
            value = source[field]
            if field == "summary" and value is None:
                target[field] = None
            else:
                text = bounded_text(value, field, maximum, required=True)
                assert text is not None
                target[field] = text


def validate_scopes(nodes: Sequence[dict[str, object]], document_id: str, name: str) -> None:
    for node in nodes:
        for field in ("document_id", "doc_id"):
            if field in node and node[field] != document_id:
                raise input_error("tree node declares a different document identity")
        if "document_name" in node and node["document_name"] != name:
            raise input_error("tree node declares a different document name")
        if "document_scope" in node and node["document_scope"] not in {document_id, name}:
            raise input_error("tree node declares a different document scope")
        children = node.get("nodes", [])
        if isinstance(children, list):
            validate_scopes(children, document_id, name)


def identity_node(node: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in node.items():
        if key in _SCOPE_FIELDS:
            continue
        if key == "nodes" and isinstance(value, list):
            result[key] = [identity_node(child) for child in value]
        else:
            result[key] = value
    return result


def page_index(value: object, page_count: int, field: str) -> int:
    if type(value) is not int or not 1 <= value <= page_count:
        raise input_error(f"{field} must be a valid 1-based page number")
    return value


def bounded_text(value: object, field: str, maximum: int, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise input_error(f"{field} must be a non-empty string")
    if utf8_size(value, field) > maximum:
        raise input_error(f"{field} exceeds its size limit")
    return value


def utf8_size(value: str, field: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise input_error(f"{field} contains invalid Unicode") from exc


def input_error(reason: str) -> DataValidationError:
    return DataValidationError(
        "structural_index_input_invalid",
        "Prepared document is invalid.",
        details={"reason": reason},
    )


def integrity_error(reason: str) -> DataValidationError:
    return DataValidationError(
        "structural_index_integrity_invalid",
        "Stored structural index failed integrity validation.",
        details={"reason": reason},
    )
