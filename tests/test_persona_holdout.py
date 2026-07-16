from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_sample_reader import ParsedCodexSampleFile
from ynoy.errors import DataValidationError
from ynoy.persona_study.holdout import file_receipt
from ynoy.persona_study.source import load_protected_study_source

_NOW = datetime(2026, 3, 1, tzinfo=UTC)


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
