from __future__ import annotations

import json
from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.private_files import create_private_file, create_private_parents
from ynoy.structural_index import PreparedDocument, StructuralIndex


def _bundle() -> PreparedDocument:
    return PreparedDocument(
        name="Shared synthetic guide",
        description="Same prepared content in both storage planes.",
        pages=("Exact source page ✓", "Second exact page."),
        tree={
            "node_id": "root",
            "title": "Source chapter",
            "start_index": 1,
            "end_index": 2,
            "summary": "Navigation only",
        },
    )


def _artifact(index: StructuralIndex, document_id: str) -> Path:
    return index.root / f"{document_id}.json"


def _copy_into_private_index(
    destination: Path, private_root: Path, content: bytes
) -> None:
    create_private_parents(destination.parent, private_root=private_root)
    create_private_file(destination, private_root=private_root)
    destination.write_bytes(content)


def test_same_document_has_same_identity_and_page_hash_in_separate_planes(
    tmp_path: Path,
) -> None:
    bundle = _bundle()
    private = StructuralIndex(tmp_path, synthetic=False)
    synthetic = StructuralIndex(tmp_path, synthetic=True)
    private_ref = private.import_document(bundle)
    synthetic_ref = synthetic.import_document(bundle)

    assert private_ref.document_id == synthetic_ref.document_id
    assert private.root != synthetic.root
    private_payload = json.loads(_artifact(private, private_ref.document_id).read_text("utf-8"))
    synthetic_payload = json.loads(
        _artifact(synthetic, synthetic_ref.document_id).read_text("utf-8")
    )
    assert private_payload["schema_version"] == "ynoy-structural-index/0.2"
    assert synthetic_payload["schema_version"] == "ynoy-structural-index/0.2"
    assert private_payload["data_plane"] == "private"
    assert synthetic_payload["data_plane"] == "public_synthetic"
    assert private_payload["document_id"] == synthetic_payload["document_id"]

    private_pages = private.read_pages(private_ref.document_id, (1, 2))
    synthetic_pages = synthetic.read_pages(synthetic_ref.document_id, (1, 2))
    assert private_pages == synthetic_pages
    assert tuple(page.content_sha256 for page in private_pages) == tuple(
        page.content_sha256 for page in synthetic_pages
    )
    assert tuple(page.text for page in private_pages) == (
        "Exact source page ✓",
        "Second exact page.",
    )


@pytest.mark.parametrize(
    ("source_synthetic", "destination_synthetic"),
    [(True, False), (False, True)],
    ids=("synthetic-to-private", "private-to-synthetic"),
)
def test_cross_plane_copy_is_rejected_without_overwrite(
    tmp_path: Path, source_synthetic: bool, destination_synthetic: bool
) -> None:
    bundle = _bundle()
    source = StructuralIndex(tmp_path, synthetic=source_synthetic)
    reference = source.import_document(bundle)
    copied = _artifact(source, reference.document_id).read_bytes()
    destination_index = StructuralIndex(tmp_path, synthetic=destination_synthetic)
    destination = _artifact(destination_index, reference.document_id)
    _copy_into_private_index(destination, tmp_path, copied)
    original_bytes = destination.read_bytes()

    with pytest.raises(DataValidationError) as blocked_read:
        destination_index.read_pages(reference.document_id, (1,))
    assert blocked_read.value.code == "structural_index_integrity_invalid"
    with pytest.raises(DataValidationError) as blocked_import:
        destination_index.import_document(bundle)
    assert blocked_import.value.code == "structural_index_integrity_invalid"
    assert destination.read_bytes() == original_bytes


def test_legacy_unlabelled_v01_envelope_fails_closed(tmp_path: Path) -> None:
    source = StructuralIndex(tmp_path, synthetic=True)
    reference = source.import_document(_bundle())
    legacy = json.loads(_artifact(source, reference.document_id).read_text("utf-8"))
    legacy["schema_version"] = "ynoy-structural-index/0.1"
    legacy.pop("data_plane")
    legacy_bytes = json.dumps(legacy, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    legacy_root = tmp_path / "legacy"
    destination_index = StructuralIndex(legacy_root, synthetic=True)
    destination = _artifact(destination_index, reference.document_id)
    _copy_into_private_index(destination, legacy_root, legacy_bytes)
    before = destination.read_bytes()
    with pytest.raises(DataValidationError) as blocked:
        destination_index.read_pages(reference.document_id, (1,))
    assert blocked.value.code == "structural_index_integrity_invalid"
    assert destination.read_bytes() == before
