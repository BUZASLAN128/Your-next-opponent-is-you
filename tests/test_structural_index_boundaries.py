from __future__ import annotations

from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.structural_index import PreparedDocument, StructuralIndex
from ynoy.structural_index.validation import (
    MAX_DEPTH,
    MAX_DESCRIPTION_BYTES,
    MAX_DOCUMENT_BYTES,
    MAX_NAME_BYTES,
    MAX_NODES,
    MAX_PAGE_BYTES,
    MAX_SUMMARY_BYTES,
    MAX_TITLE_BYTES,
)


def _node(node_id: str, *, children: list[dict[str, object]] | None = None) -> dict[str, object]:
    node: dict[str, object] = {
        "node_id": node_id,
        "title": "Synthetic title",
        "start_index": 1,
        "end_index": 1,
    }
    if children is not None:
        node["nodes"] = children
    return node


def _deep_tree(depth: int) -> dict[str, object]:
    tree = _node(f"depth-{depth}")
    for level in range(depth - 1, 0, -1):
        tree = _node(f"depth-{level}", children=[tree])
    return tree


def _prepared(tree: object, *, name: str = "Boundary fixture") -> PreparedDocument:
    return PreparedDocument(name=name, pages=("Exact page.",), tree=tree)


def test_maximum_depth_import_roundtrips_and_next_depth_leaves_no_artifact(
    tmp_path: Path,
) -> None:
    index = StructuralIndex(tmp_path / "depth", synthetic=True)
    accepted = _deep_tree(MAX_DEPTH)
    document = index.import_document(_prepared(accepted))
    assert index.read_tree(document.document_id) == accepted

    with pytest.raises(DataValidationError) as blocked:
        index.import_document(_prepared(_deep_tree(MAX_DEPTH + 1), name="Too deep"))
    assert blocked.value.code == "structural_index_input_invalid"
    assert index.list_documents() == [document]


def test_maximum_node_count_lists_after_reload_and_next_node_count_is_rejected(
    tmp_path: Path,
) -> None:
    index = StructuralIndex(tmp_path / "nodes", synthetic=True)
    accepted = _node("root", children=[_node(f"child-{number}") for number in range(MAX_NODES - 1)])
    document = index.import_document(_prepared(accepted))
    reopened = StructuralIndex(tmp_path / "nodes", synthetic=True)
    assert reopened.list_documents() == [document]

    oversized = _node(
        "root-too-wide", children=[_node(f"extra-{number}") for number in range(MAX_NODES)]
    )
    with pytest.raises(DataValidationError) as blocked:
        index.import_document(_prepared(oversized, name="Too many nodes"))
    assert blocked.value.code == "structural_index_input_invalid"
    assert reopened.list_documents() == [document]


def test_maximum_optional_metadata_and_page_bytes_roundtrip(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / "maximal", synthetic=True)
    name = "N" * MAX_NAME_BYTES
    description = "D" * MAX_DESCRIPTION_BYTES
    pages = ("P" * MAX_PAGE_BYTES, "Second exact page.")
    base_tree = _node("root")
    base_tree["title"] = "T" * MAX_TITLE_BYTES
    base_tree["summary"] = "S" * MAX_SUMMARY_BYTES
    base = PreparedDocument(name=name, description=description, pages=pages, tree=base_tree)
    expected = index.import_document(base)
    annotated_tree = {
        **base_tree,
        "document_id": expected.document_id,
        "doc_id": expected.document_id,
        "document_name": name,
        "document_scope": name,
    }
    annotated = PreparedDocument(
        name=name, description=description, pages=pages, tree=annotated_tree
    )

    scoped_index = StructuralIndex(tmp_path / "scoped", synthetic=True)
    assert scoped_index.import_document(base) == expected
    reference = scoped_index.import_document(annotated)
    assert reference == expected
    assert scoped_index.import_document(annotated) == reference
    assert scoped_index.read_tree(reference.document_id) == base_tree
    read_pages = scoped_index.read_pages(reference.document_id, (1, 2))
    assert tuple(page.text for page in read_pages) == pages
    assert len(pages[0].encode("utf-8")) + len(pages[1].encode("utf-8")) < MAX_DOCUMENT_BYTES


def test_wrong_scope_annotation_is_rejected_without_adding_document(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / "scope", synthetic=True)
    good = index.import_document(_prepared(_node("good")))
    bad_tree = {
        **_node("bad"),
        "document_id": "0" * 64,
        "document_name": "another source",
    }
    with pytest.raises(DataValidationError) as blocked:
        index.import_document(_prepared(bad_tree, name="Wrong scope"))
    assert blocked.value.code == "structural_index_input_invalid"
    assert index.list_documents() == [good]
