from __future__ import annotations

import json
from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.structural_index import PreparedDocument, StructuralIndex


def _stored_path(index: StructuralIndex, document_id: str) -> Path:
    return index.root / f"{document_id}.json"


def _import_one(index: StructuralIndex) -> str:
    document = PreparedDocument(
        name="integrity fixture",
        pages=("Exact durable source ✓.",),
        tree={"node_id": "root", "title": "Root", "start_index": 1, "end_index": 1},
    )
    first = index.import_document(document)
    assert index.import_document(document) == first
    return first.document_id


@pytest.mark.parametrize(
    "tampered",
    [
        b'{"document_id":"duplicate","document_id":"key"}',
        b'{"number":NaN}',
        b'{"number":Infinity}',
        b'{"number":1e999}',
    ],
    ids=("duplicate-json-key", "nan", "infinity", "overflow-float"),
)
def test_non_strict_or_duplicate_json_is_rejected(
    tmp_path: Path, tampered: bytes
) -> None:
    index = StructuralIndex(tmp_path / "private", synthetic=True)
    document_id = _import_one(index)
    _stored_path(index, document_id).write_bytes(tampered)

    with pytest.raises(DataValidationError) as blocked:
        index.read_tree(document_id)
    assert blocked.value.code == "structural_index_integrity_invalid"


def test_stored_schema_or_page_tampering_breaks_integrity(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / "private", synthetic=True)
    document_id = _import_one(index)
    path = _stored_path(index, document_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["foreign_field"] = "unexpected"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationError) as schema_error:
        index.read_tree(document_id)
    assert schema_error.value.code == "structural_index_integrity_invalid"

    payload.pop("foreign_field")
    payload["pages"][0]["text"] = "Altered source ✓."
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationError) as content_error:
        index.read_pages(document_id, (1,))
    assert content_error.value.code == "structural_index_integrity_invalid"


def test_list_documents_repeatedly_and_after_reopen(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / "private", synthetic=True)
    document_id = _import_one(index)
    expected = index.list_documents()
    assert len(expected) == 1
    assert expected[0].document_id == document_id
    assert index.list_documents() == expected

    reopened = StructuralIndex(tmp_path / "private", synthetic=True)
    assert reopened.list_documents() == expected
