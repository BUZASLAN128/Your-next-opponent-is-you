from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from support.persona_study import synthetic_codex_study_root

from ynoy.cli.context import CommandContext
from ynoy.cli.main import main
from ynoy.models.persona_harvest import HarvestLimits
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest import prepare_harvest
from ynoy.persona_study.prepare import prepare_persona_study


def _limits() -> HarvestLimits:
    return HarvestLimits(
        max_files=4,
        max_total_input_bytes=20_000,
        max_file_bytes=10_000,
        max_line_bytes=8_000,
        max_records=1_000,
        max_events=1_000,
        max_entries=256,
    )


def _prepare_inputs(tmp_path: Path) -> tuple[Path, Path, str, datetime, tuple[str, ...]]:
    source, sentinels = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    now = datetime(2026, 7, 18, tzinfo=UTC)
    study = prepare_persona_study(source, private, synthetic=True, evaluation_time=now)
    return source, private, study.manifest.study_id, now, sentinels


def test_harvest_writes_private_manifest_checkpoint_review_and_labels(tmp_path: Path) -> None:
    source, private, study_id, now, _ = _prepare_inputs(tmp_path)
    result = prepare_harvest(
        source,
        private,
        study_id,
        synthetic=True,
        limits=_limits(),
        evaluation_time=now,
    )

    index = PersonaStudyStore(private, real_data=False, evaluation_time=now).read_index(
        result.manifest.run_id
    )
    paths = {entry.relative_path for entry in index.entries}
    assert "evaluator/harvest-manifest.json" in paths
    assert any(path.startswith("evaluator/harvest-checkpoint-") for path in paths)
    assert result.review_path.is_file() and result.labels_path.is_file()
    assert result.checkpoint.database_used is False
    assert result.checkpoint.model_provider_used is False
    assert result.checkpoint.automatic_core_promotion is False
    assert all(item.claim_holder == "unknown" for item in result.checkpoint.candidates)


def test_unchanged_source_regeneration_has_identical_candidate_selection(tmp_path: Path) -> None:
    source, private, study_id, now, _ = _prepare_inputs(tmp_path)
    first = prepare_harvest(
        source, private, study_id, synthetic=True, limits=_limits(), evaluation_time=now
    )
    second = prepare_harvest(
        source, private, study_id, synthetic=True, limits=_limits(), evaluation_time=now
    )

    assert first.manifest.run_id != second.manifest.run_id
    assert first.checkpoint.candidates == second.checkpoint.candidates
    assert first.checkpoint.cursor.selector_config_sha256 == (
        second.checkpoint.cursor.selector_config_sha256
    )


def test_delete_run_removes_all_harvest_artifacts(tmp_path: Path) -> None:
    source, private, study_id, now, _ = _prepare_inputs(tmp_path)
    result = prepare_harvest(
        source, private, study_id, synthetic=True, limits=_limits(), evaluation_time=now
    )
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)

    deleted = store.delete_run(result.manifest.run_id)
    store.require_absent(result.manifest.run_id)

    assert deleted >= 1
    assert not any(result.manifest.run_id in path.name for path in store.tombstones.iterdir())


def test_harvest_cli_never_calls_database_or_model_provider(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source, private, study_id, _, sentinels = _prepare_inputs(tmp_path)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("harvester must not call database or model provider")

    monkeypatch.setattr(CommandContext, "database", forbidden)
    monkeypatch.setattr(CommandContext, "setup_database", forbidden)
    monkeypatch.setattr("ynoy.reasoner.LocalOpenAIReasoner.__init__", forbidden)
    monkeypatch.setattr("ynoy.reasoner.DeterministicReasoner.complete", forbidden)

    code = main(
        [
            "--indent",
            "0",
            "--private-root",
            str(private),
            "study",
            "harvest",
            str(source),
            study_id,
            "--synthetic",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0 and captured.err == "" and payload["ok"] is True
    assert payload["result"]["database_used"] is False
    assert payload["result"]["model_provider_used"] is False
    assert payload["result"]["persona_quality_claimed"] is False
    assert all(value not in captured.out for value in sentinels)
