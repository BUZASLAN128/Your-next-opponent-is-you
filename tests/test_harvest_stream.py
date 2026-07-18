# ruff: noqa: RUF001 -- Turkish judgment fixtures mirror the selector vocabulary.

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from support.harvest import write_rollout

from ynoy.corpus.codex import SYNTHETIC_MARKER
from ynoy.errors import DataValidationError
from ynoy.models.persona_harvest import HarvestLimits
from ynoy.persona_study.harvest_contract import seal_harvest_manifest
from ynoy.persona_study.harvest_processor import process_harvest_checkpoint


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic-codex"
    (root / "sessions").mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(SYNTHETIC_MARKER)
    return root


def _manifest(limits: HarvestLimits):
    now = datetime(2026, 2, 1, tzinfo=UTC)
    return seal_harvest_manifest(
        run_id="4" * 64,
        source_study_id="5" * 64,
        freeze_sha256="6" * 64,
        boundary_ns=int((now + timedelta(days=1)).timestamp() * 1_000_000_000),
        stable_before_ns=int(now.timestamp() * 1_000_000_000),
        limits=limits,
        created_at=now,
        expires_at=now + timedelta(days=1),
        synthetic=True,
    )


def _limits(**changes: int | float) -> HarvestLimits:
    values = dict(changes)
    total_bytes = int(values.pop("max_total_input_bytes", 10_000))
    file_bytes = int(values.pop("max_file_bytes", min(10_000, total_bytes)))
    records = int(values.pop("max_records", 20))
    events = int(values.pop("max_events", 20))
    entries = int(values.pop("max_entries", 64))
    return HarvestLimits(
        max_files=2,
        max_total_input_bytes=total_bytes,
        max_file_bytes=file_bytes,
        max_line_bytes=min(8_000, file_bytes),
        max_records=records,
        max_events=events,
        max_entries=entries,
        **values,
    )


def _write_source(root: Path, *, identity: int = 1) -> Path:
    name = f"rollout-2026-01-02T03-04-05-{UUID(int=identity)}.jsonl"
    return write_rollout(
        root,
        name,
        (
            ("assistant", "Here is context."),
            ("user", "Yanlış, düzelt ve kanıt göster."),
            ("assistant", "Another context turn."),
            ("user", "Bunu onaylıyorum, test et."),
        ),
    )


def test_record_budget_returns_partial_cursor_and_resume_is_deterministic(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_source(root)
    manifest = _manifest(_limits(max_wall_seconds=1.0))
    ticks = iter((0.0, 0.0, 0.0, 0.0, 2.0))
    first = process_harvest_checkpoint(
        root,
        manifest,
        clock=lambda: next(ticks, 2.0),
    )

    assert first.checkpoint.cursor.status == "partial"
    assert first.checkpoint.checkpoint_record_count == 2
    assert first.checkpoint.cursor.last_file is not None
    assert first.checkpoint.cursor.last_file.next_byte_offset > 0

    resumed = process_harvest_checkpoint(
        root,
        manifest,
        first.checkpoint,
        clock=lambda: 0.0,
    )
    assert resumed.checkpoint.cursor.revision == 2
    assert [item.candidate_id for item in resumed.checkpoint.candidates] == [
        item.candidate_id
        for item in process_harvest_checkpoint(
            root, manifest, clock=lambda: 0.0
        ).checkpoint.candidates
    ]


def test_replay_of_same_partial_checkpoint_is_idempotent_in_selection(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_source(root)
    manifest = _manifest(_limits(max_records=2))
    first = process_harvest_checkpoint(root, manifest, clock=lambda: 0.0)
    replay = process_harvest_checkpoint(root, manifest, first.checkpoint, clock=lambda: 0.0)

    assert (
        replay.checkpoint.checkpoint_sha256
        == process_harvest_checkpoint(
            root, manifest, first.checkpoint, clock=lambda: 0.0
        ).checkpoint.checkpoint_sha256
    )
    assert len({item.candidate_id for item in replay.checkpoint.candidates}) == len(
        replay.checkpoint.candidates
    )


def test_source_mutation_after_checkpoint_fails_closed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    source = _write_source(root)
    manifest = _manifest(_limits(max_records=2))
    first = process_harvest_checkpoint(root, manifest, clock=lambda: 0.0)
    with source.open("ab") as stream:
        stream.write(b"mutation\n")
    os.utime(source, None)

    with pytest.raises(DataValidationError) as error:
        process_harvest_checkpoint(root, manifest, first.checkpoint, clock=lambda: 0.0)
    assert error.value.code == "codex_harvest_source_changed"


def test_wall_time_limit_stops_without_unbounded_reads(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_source(root)
    ticks = iter((0.0, 0.0, 0.5, 0.5))
    result = process_harvest_checkpoint(
        root,
        _manifest(_limits(max_wall_seconds=0.1)),
        clock=lambda: next(ticks, 1.0),
    )

    assert result.checkpoint.cursor.status == "partial"
    assert result.checkpoint.checkpoint_record_count <= 1


def test_metadata_discovery_entry_budget_fails_before_unbounded_scan(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_source(root)
    (root / "sessions" / "2026" / "01" / "02" / "extra.txt").write_text("ignored")

    with pytest.raises(DataValidationError) as error:
        process_harvest_checkpoint(root, _manifest(_limits(max_entries=3)), clock=lambda: 0.0)

    assert error.value.code == "codex_harvest_entry_limit"


@pytest.mark.parametrize(
    ("field", "value"),
    [("max_total_input_bytes", 1), ("max_records", 1), ("max_events", 1)],
)
def test_small_checkpoint_limits_remain_within_budget(
    tmp_path: Path, field: str, value: int
) -> None:
    root = _root(tmp_path)
    _write_source(root)
    result = process_harvest_checkpoint(
        root, _manifest(_limits(**{field: value})), clock=lambda: 0.0
    )

    if field == "max_total_input_bytes":
        assert result.checkpoint.checkpoint_input_bytes <= value
    elif field == "max_records":
        assert result.checkpoint.checkpoint_record_count <= value
    else:
        assert result.checkpoint.checkpoint_event_count <= value
