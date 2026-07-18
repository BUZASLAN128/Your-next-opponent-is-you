from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_sample_reader import ParsedCodexSampleFile
from ynoy.errors import DataValidationError
from ynoy.models import DataClass
from ynoy.persona_study.holdout import (
    HoldoutPlan,
    _component_lineages,
    _LineageFile,
    _read_lineage,
    build_protected_holdout,
    file_receipt,
)
from ynoy.persona_study.source import load_protected_study_source
from ynoy.util import sha256_text

_NOW = datetime(2026, 3, 1, tzinfo=UTC)


def _synthetic_lineage(thread: str, parent: str | None, *, index: int) -> _LineageFile:
    relative = Path(f"synthetic-{index:02d}.jsonl")
    return _LineageFile(
        item=DiscoveredCodexFile(
            partition="sessions",
            path=relative,
            relative=relative,
            file_bytes=1,
            modified_ns=index,
            device=0,
            inode=index,
        ),
        source_receipt=sha256_text(f"source:{index}"),
        thread_receipt=sha256_text(f"holdout-thread:{thread}"),
        parent_receipt=(sha256_text(f"holdout-thread:{parent}") if parent is not None else None),
        session_start_ns=index,
    )


def _write_session_meta(root: Path, *, thread: str, parent: str, index: int) -> DiscoveredCodexFile:
    relative = Path(
        f"rollout-2026-01-{index:02d}T03-04-05-00000000-0000-0000-0000-0000000000{index:02d}.jsonl"
    )
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": thread, "parent_thread_id": parent},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metadata = path.stat()
    return DiscoveredCodexFile(
        partition="sessions",
        path=path,
        relative=relative,
        file_bytes=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )


def test_holdout_is_later_disjoint_and_never_dialogue_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = synthetic_codex_study_root(tmp_path)
    parsed_receipts: list[str] = []
    from ynoy.persona_study import source as source_module

    original = source_module.parse_codex_sample_file

    def tracked(item: DiscoveredCodexFile, **kwargs: object) -> ParsedCodexSampleFile:
        parsed_receipts.append(file_receipt(item))
        return cast(Any, original)(item, **kwargs)

    monkeypatch.setattr(source_module, "parse_codex_sample_file", tracked)

    sample, freeze = load_protected_study_source(root, synthetic=True, evaluation_time=_NOW)

    holdout_receipts = {item.source_receipt for item in freeze.sources}
    assert 8 <= freeze.selected_file_count <= 12
    assert sample.selected_file_count == 24
    assert set(sample.selected_file_receipts) == set(parsed_receipts)
    assert set(parsed_receipts).isdisjoint(holdout_receipts)
    assert sample.selected_max_session_start_ns < freeze.boundary_session_start_ns
    assert freeze.ordering_basis == "canonical_rollout_filename_time"
    assert freeze.event_time_order_verified is False
    assert freeze.dialogue_content_opened is False
    assert freeze.predictor_access_granted is False
    assert freeze.target_labels_created is False
    assert freeze.annotation_source_overlap is False
    assert freeze.explicit_lineage_overlap is False
    assert freeze.duplicate_content_overlap_status == "unchecked_until_sealed_open"


def test_holdout_freeze_replays_identically(tmp_path: Path) -> None:
    root, _ = synthetic_codex_study_root(tmp_path)

    first_sample, first = load_protected_study_source(root, synthetic=True, evaluation_time=_NOW)
    second_sample, second = load_protected_study_source(root, synthetic=True, evaluation_time=_NOW)

    assert first.freeze_sha256 == second.freeze_sha256
    assert first.sources == second.sources
    assert first_sample.source_snapshot_sha256 == second_sample.source_snapshot_sha256
    assert first_sample.selected_file_receipts == second_sample.selected_file_receipts


def test_holdout_requires_earlier_annotation_history(tmp_path: Path) -> None:
    root, _ = synthetic_codex_study_root(tmp_path)
    files = sorted(root.rglob("*.jsonl"))
    for path in files[:-20]:
        path.unlink()

    with pytest.raises(DataValidationError) as error:
        load_protected_study_source(root, synthetic=True, evaluation_time=_NOW)

    assert error.value.code in {
        "persona_holdout_annotation_history_insufficient",
        "persona_holdout_source_insufficient",
    }


def test_missing_parent_is_shared_opaque_anchor_without_crossing_siblings() -> None:
    values = (
        _synthetic_lineage("thread-a", "missing-parent", index=1),
        _synthetic_lineage("thread-b", "missing-parent", index=2),
        _synthetic_lineage("thread-c", "different-parent", index=3),
    )

    resolved = _component_lineages(values)

    assert resolved[0].component_receipt == resolved[1].component_receipt
    assert resolved[0].component_receipt != resolved[2].component_receipt


def test_lineage_cycle_fails_closed() -> None:
    values = (
        _synthetic_lineage("thread-a", "thread-b", index=1),
        _synthetic_lineage("thread-b", "thread-a", index=2),
    )

    with pytest.raises(DataValidationError) as error:
        _component_lineages(values)

    assert error.value.code.startswith("persona_holdout_lineage")


def test_invalid_session_metadata_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "invalid-session.jsonl"
    path.write_text('{"type":"session_meta","payload":{"id":42}}\n', encoding="utf-8")
    metadata = path.stat()
    item = DiscoveredCodexFile(
        partition="sessions",
        path=path,
        relative=Path(path.name),
        file_bytes=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )

    with pytest.raises(DataValidationError) as error:
        _read_lineage(item)

    assert error.value.code == "persona_holdout_thread_id_required"


@pytest.mark.parametrize(
    "parent",
    [
        pytest.param([], id="list"),
        pytest.param("", id="blank"),
    ],
)
def test_invalid_parent_metadata_fails_closed(tmp_path: Path, parent: object) -> None:
    relative = Path("rollout-2026-01-01T03-04-05-00000000-0000-0000-0000-000000000001.jsonl")
    path = tmp_path / relative
    path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "synthetic-thread", "parent_thread_id": parent},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metadata = path.stat()
    item = DiscoveredCodexFile(
        partition="sessions",
        path=path,
        relative=relative,
        file_bytes=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )

    with pytest.raises(DataValidationError) as error:
        _read_lineage(item)

    assert error.value.code == "persona_holdout_parent_thread_id_invalid"


def test_explicit_null_parent_is_an_opaque_root(tmp_path: Path) -> None:
    relative = Path("rollout-2026-01-01T03-04-05-00000000-0000-0000-0000-000000000002.jsonl")
    path = tmp_path / relative
    path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "synthetic-root", "parent_thread_id": None},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    metadata = path.stat()
    item = DiscoveredCodexFile(
        partition="sessions",
        path=path,
        relative=relative,
        file_bytes=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )

    lineage = _read_lineage(item)

    assert lineage.parent_receipt is None


def test_holdout_rejects_shared_missing_parent_anchor_across_annotation_boundary(
    tmp_path: Path,
) -> None:
    holdout_item = _write_session_meta(
        tmp_path, thread="synthetic-holdout", parent="synthetic-missing", index=1
    )
    annotation_item = _write_session_meta(
        tmp_path, thread="synthetic-annotation", parent="synthetic-missing", index=2
    )
    annotation_lineage, holdout_lineage = _component_lineages(
        (_read_lineage(annotation_item), _read_lineage(holdout_item))
    )
    serialized = json.dumps(
        [
            {
                "source_receipt": item.source_receipt,
                "thread_receipt": item.thread_receipt,
                "parent_receipt": item.parent_receipt,
                "component_receipt": item.component_receipt,
            }
            for item in (annotation_lineage, holdout_lineage)
        ],
        sort_keys=True,
    )
    assert all(
        raw not in serialized
        for raw in ("synthetic-holdout", "synthetic-annotation", "synthetic-missing")
    )
    assert holdout_lineage.source_receipt == file_receipt(holdout_item)
    plan = HoldoutPlan((), (holdout_lineage,), holdout_lineage.session_start_ns)

    with pytest.raises(DataValidationError) as error:
        build_protected_holdout(
            plan,
            (annotation_item,),
            sha256_text("annotation-selection"),
            created_at=_NOW,
            data_class=DataClass.PUBLIC_SYNTHETIC,
        )

    assert error.value.code == "persona_holdout_lineage_overlap"
