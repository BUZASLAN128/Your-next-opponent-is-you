from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.structural_index import PreparedDocument, StructuralIndex


def _bundle(
    *, start: int = 1, end: int = 2, node_id: str = "chapter-a", summary: str = "Summary only."
) -> PreparedDocument:
    return PreparedDocument(
        name="synthetic handbook",
        description="Synthetic test document",
        pages=("Exact source on page one.", "Exact source on page two."),
        tree={
            "node_id": node_id,
            "title": "Two page chapter",
            "start_index": start,
            "end_index": end,
            "summary": summary,
        },
    )


def test_import_reads_exact_scoped_page_sources_and_preserves_stable_document(
    tmp_path: Path,
) -> None:
    index = StructuralIndex(tmp_path / "index", synthetic=True)
    document = index.import_document(_bundle())

    assert index.list_documents() == [document]
    assert index.read_tree(document.document_id) == _bundle().tree
    node = index.read_nodes(document.document_id, ("chapter-a",))[0]
    assert node.summary == "Summary only."
    assert tuple(page.text for page in node.pages) == (
        "Exact source on page one.",
        "Exact source on page two.",
    )
    assert tuple(page.source_ref for page in node.pages) == (
        f"{document.document_id}#page=1",
        f"{document.document_id}#page=2",
    )
    assert all(page.content_sha256 for page in node.pages)

    reopened = StructuralIndex(tmp_path / "index", synthetic=True)
    assert reopened.list_documents() == [document]
    assert reopened.read_pages(document.document_id, (1, 2)) == list(node.pages)


@pytest.mark.parametrize(
    ("start", "end", "node_id", "error_code"),
    [
        (0, 1, "zero", "structural_index_input_invalid"),
        (1, 3, "past-end", "structural_index_input_invalid"),
        (2, 1, "reversed", "structural_index_input_invalid"),
        (1, 1, "duplicate", "structural_index_input_invalid"),
    ],
)
def test_invalid_page_spans_and_duplicate_node_ids_fail_closed(
    tmp_path: Path, start: int, end: int, node_id: str, error_code: str
) -> None:
    index = StructuralIndex(tmp_path / "index", synthetic=True)
    bundle = _bundle(start=start, end=end, node_id=node_id)
    if node_id == "duplicate":
        bundle = replace(
            bundle,
            tree=[
                    {
                        "node_id": "duplicate",
                        "title": "First",
                        "start_index": 1,
                        "end_index": 1,
                    },
                    {
                        "node_id": "duplicate",
                        "title": "Second",
                        "start_index": 2,
                        "end_index": 2,
                    },
            ],
        )

    with pytest.raises(DataValidationError) as blocked:
        index.import_document(bundle)
    assert blocked.value.code == error_code
    assert index.list_documents() == []


def test_overlapping_spans_and_forest_roots_are_valid(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / "index", synthetic=True)
    bundle = PreparedDocument(
        name="overlapping synthetic chapters",
        pages=("Page one", "Page two"),
        tree=(
            {"node_id": "first", "title": "First", "start_index": 1, "end_index": 2},
            {"node_id": "second", "title": "Second", "start_index": 2, "end_index": 2},
        ),
    )

    document = index.import_document(bundle)
    assert index.read_tree(document.document_id) == list(bundle.tree)
    first = index.read_nodes(document.document_id, ("first",))[0]
    second = index.read_nodes(document.document_id, ("second",))[0]
    assert tuple(page.page_number for page in first.pages) == (1, 2)
    assert tuple(page.page_number for page in second.pages) == (2,)
