from __future__ import annotations

import socket
from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.reasoner import LocalOpenAIReasoner
from ynoy.structural_index import PreparedDocument, StructuralIndex


def _document(*, tree: object | None = None) -> PreparedDocument:
    return PreparedDocument(
        name="synthetic source",
        pages=("Exact first page.", "Exact second page.", "Exact third page."),
        tree=tree
        if tree is not None
        else {
            "node_id": "root",
            "title": "Root",
            "start_index": 1,
            "end_index": 3,
            "nodes": [
                {"node_id": "leaf", "title": "Leaf", "start_index": 2, "end_index": 2}
            ],
        },
    )


@pytest.mark.parametrize(
    ("operation", "selection", "code"),
    [
        ("pages", (0,), "structural_index_input_invalid"),
        ("pages", (4,), "structural_index_input_invalid"),
        ("pages", (1, 1), "structural_index_page_ref_duplicate"),
        ("pages", (True,), "structural_index_input_invalid"),
        ("nodes", ("missing",), "structural_index_node_not_found"),
        ("nodes", ("leaf", "leaf"), "structural_index_node_ref_duplicate"),
        ("nodes", ("",), "structural_index_input_invalid"),
    ],
)
def test_invalid_scope_and_page_or_node_selections_are_rejected(
    tmp_path: Path, operation: str, selection: tuple[object, ...], code: str
) -> None:
    index = StructuralIndex(tmp_path / "private", synthetic=True)
    document = index.import_document(_document())
    with pytest.raises(DataValidationError) as blocked:
        if operation == "pages":
            index.read_pages(document.document_id, selection)  # type: ignore[arg-type]
        else:
            index.read_nodes(document.document_id, selection)  # type: ignore[arg-type]
    assert blocked.value.code == code


def test_scope_binding_cycle_and_unicode_input_fail_closed(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / "private", synthetic=True)
    mismatch = _document(
        tree={
            "node_id": "scoped",
            "title": "Scoped",
            "start_index": 1,
            "end_index": 1,
            "document_name": "another document",
        }
    )
    with pytest.raises(DataValidationError, match="Prepared document"):
        index.import_document(mismatch)

    cyclic: dict[str, object] = {
        "node_id": "cycle",
        "title": "Cycle",
        "start_index": 1,
        "end_index": 1,
    }
    cyclic["nodes"] = [cyclic]
    for bundle in (
        _document(tree=cyclic),
        _document(tree={"node_id": "bad\ud800", "title": "Bad", "start_index": 1, "end_index": 1}),
    ):
        with pytest.raises(DataValidationError):
            index.import_document(bundle)
    assert index.list_documents() == []


def test_structural_reads_need_no_network_and_return_source_not_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("structural index attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)

    def no_model_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("structural index attempted a model call")

    monkeypatch.setattr(LocalOpenAIReasoner, "complete", no_model_call)
    index = StructuralIndex(tmp_path / "private", synthetic=True)
    document = index.import_document(_document())
    node = index.read_nodes(document.document_id, ("leaf",))[0]
    assert tuple(page.text for page in node.pages) == ("Exact second page.",)
    assert node.pages[0].content_sha256
    assert "summary" not in node.pages[0].text
    assert StructuralIndex(tmp_path / "private", synthetic=True).read_pages(
        document.document_id, (2,)
    )[0] == node.pages[0]
