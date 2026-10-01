from __future__ import annotations

from pathlib import Path

import pytest

import ynoy.full_persona.run_lock as run_lock
import ynoy.structural_index.plane_storage as plane_storage
from ynoy.errors import DataValidationError
from ynoy.structural_index import PreparedDocument, StructuralIndex


def _bundle(name: str) -> PreparedDocument:
    return PreparedDocument(
        name=name,
        pages=(f"Exact source for {name}.",),
        tree={"node_id": "root", "title": "Root", "start_index": 1, "end_index": 1},
    )


def test_structural_import_refuses_a_new_document_past_the_configured_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plane_storage, "_MAX_DOCUMENTS", 1)
    index = StructuralIndex(tmp_path / "index", synthetic=True)
    first = index.import_document(_bundle("first"))

    with pytest.raises(DataValidationError) as rejected:
        index.import_document(_bundle("second"))

    assert rejected.value.code == "structural_index_document_limit"
    assert index.list_documents() == [first]


def test_lock_marker_is_prepared_only_after_the_os_lock_is_acquired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    prepare = run_lock._prepare_lock_file

    def tracked_prepare(handle) -> None:
        events.append("prepare")
        prepare(handle)

    monkeypatch.setattr(run_lock, "_acquire", lambda handle: events.append("acquire"))
    monkeypatch.setattr(run_lock, "_prepare_lock_file", tracked_prepare)
    monkeypatch.setattr(run_lock, "_release", lambda handle: events.append("release"))

    with run_lock.exclusive_run_lock(tmp_path / "lock"):
        events.append("inside")

    assert events == ["acquire", "prepare", "inside", "release"]
