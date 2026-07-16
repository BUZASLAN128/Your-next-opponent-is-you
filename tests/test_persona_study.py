from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.persona_study import synthetic_codex_study_root

from ynoy.cli.context import CommandContext
from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.models import (
    ClaimHolder,
    DataClass,
    EvidenceWindow,
    ProtectedHoldoutFreeze,
    SourceAuthority,
)
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.deletion import prove_disposable_deletion
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.persona_study.render import label_template
from ynoy.persona_study.source import (
    StudySourceSample,
    load_protected_study_source,
    load_study_source,
)
from ynoy.persona_study.windows import PreparedWindows, prepare_windows
from ynoy.util import canonical_json_bytes, canonical_sha256


def _prepared_windows(tmp_path: Path) -> PreparedWindows:
    root, _ = synthetic_codex_study_root(tmp_path)
    source = load_study_source(root, synthetic=True)
    return prepare_windows(source.events, source.source_snapshot_sha256)


def _assert_unattributed_chronology(prepared: PreparedWindows) -> None:
    assert all(
        item.focus.structural_claim_holder == ClaimHolder.UNKNOWN for item in prepared.windows
    )
    assert all(
        item.focus.source_authority == SourceAuthority.USER_TURN_UNATTRIBUTED
        for item in prepared.windows
    )
    assert all(
        context.sequence_index < item.focus.sequence_index
        and context.event_time <= item.focus.event_time
        for item in prepared.windows
        for context in item.context
    )


def _assert_branch_components_do_not_cross_split(prepared: PreparedWindows) -> None:
    split_by_window = {item.window_id: item.annotation_partition for item in prepared.blind_map}
    splits_by_component: dict[str, set[str]] = {}
    for window in prepared.windows:
        splits_by_component.setdefault(window.dependency_component_id, set()).add(
            split_by_window[window.window_id]
        )
    assert prepared.dependency_component_count >= 6
    assert all(len(values) == 1 for values in splits_by_component.values())


def _assert_blind_repeat_contract(prepared: PreparedWindows) -> None:
    repeated = [item for item in prepared.blind_map if item.repeated]
    by_id = {item.window_id: item for item in prepared.windows}
    assert Counter(by_id[item.window_id].selection_arm for item in repeated) == {
        "sampled": 4,
        "challenge": 4,
    }
    cards = canonical_json_bytes([item.model_dump(mode="json") for item in prepared.presentations])
    template = canonical_json_bytes(label_template(prepared.study_id, prepared.presentations))
    hidden_fields = (
        b'"window_id"',
        b'"annotation_partition"',
        b'"repeated"',
        b'"event_id"',
        b'"content_sha256"',
        b'"event_time"',
        b'"sequence_index"',
    )
    assert all(field not in cards + template for field in hidden_fields)
    assert all(item.window_id.encode() not in cards + template for item in prepared.windows)


def test_24_plus_8_selection_is_deterministic_unattributed_and_blinded(tmp_path: Path) -> None:
    root, _ = synthetic_codex_study_root(tmp_path)
    source = load_study_source(root, synthetic=True)

    first = prepare_windows(source.events, source.source_snapshot_sha256)
    replay = prepare_windows(source.events, source.source_snapshot_sha256)

    assert len(first.windows) == 24
    assert len(first.presentations) == 32
    assert len(first.blind_map) == 32
    assert first.selection_sha256 == replay.selection_sha256
    assert first.blind_map_sha256 == replay.blind_map_sha256
    assert [item.window_sha256 for item in first.windows] == [
        item.window_sha256 for item in replay.windows
    ]
    _assert_unattributed_chronology(first)
    _assert_branch_components_do_not_cross_split(first)
    _assert_blind_repeat_contract(first)


def test_evidence_window_rejects_context_timestamp_after_focus(tmp_path: Path) -> None:
    window = _prepared_windows(tmp_path).windows[0]
    context = window.context[0].model_copy(
        update={"event_time": window.focus.event_time + timedelta(seconds=1)}
    )
    draft = window.model_copy(update={"context": (context,), "window_sha256": "0" * 64})
    payload = draft.model_dump(mode="python", exclude={"window_sha256"})
    payload["window_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"window_sha256"})
    )

    with pytest.raises(ValidationError, match="precede"):
        EvidenceWindow.model_validate(payload)


def test_evidence_window_rejects_attributed_focus_authority(tmp_path: Path) -> None:
    window = _prepared_windows(tmp_path).windows[0]
    focus = window.focus.model_copy(
        update={"source_authority": SourceAuthority.EXPLICIT_USER_STATEMENT}
    )
    draft = window.model_copy(update={"focus": focus, "window_sha256": "0" * 64})
    payload = draft.model_dump(mode="python", exclude={"window_sha256"})
    payload["window_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"window_sha256"})
    )

    with pytest.raises(ValidationError, match="unattributed"):
        EvidenceWindow.model_validate(payload)


def test_retention_purges_expired_run_and_sets_exact_seven_days(tmp_path: Path) -> None:
    source_root, _ = synthetic_codex_study_root(tmp_path)
    private_root = tmp_path / "private"
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(
        private_root, real_data=False, evaluation_time=now - timedelta(days=8)
    )
    expired_id = canonical_sha256({"expired": True})
    payload = ArtifactPayload(
        "evaluator/expired.json",
        b"{}",
        DataClass.PUBLIC_SYNTHETIC,
        (canonical_sha256("source"),),
    )
    store.write_run(
        expired_id,
        (payload,),
        created_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),
    )

    result = prepare_persona_study(source_root, private_root, synthetic=True, evaluation_time=now)

    assert result.expired_artifacts_purged == 1
    assert result.manifest.expires_at - result.manifest.created_at == timedelta(days=7)
    with pytest.raises(DataValidationError, match="not found"):
        store.read_index(expired_id)


def test_source_linked_deletion_regenerates_and_tamper_fails_closed(tmp_path: Path) -> None:
    prepared = _prepared_windows(tmp_path)
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    receipt = prove_disposable_deletion(
        store, prepared.windows[0], created_at=now, expires_at=now + timedelta(days=7)
    )

    assert receipt.first_bundle_sha256 == receipt.regenerated_bundle_sha256
    assert receipt.first_deleted_count == receipt.second_deleted_count == 4
    assert receipt.read_after_delete == "not_found"
    tombstone = store.tombstones / f"{receipt.proof_id}.json"
    assert tombstone.is_file()
    assert prepared.windows[0].focus.content.encode() not in tombstone.read_bytes()

    run_id = canonical_sha256({"tamper": True})
    dependency = canonical_sha256("tamper-source")
    store.write_run(
        run_id,
        (
            ArtifactPayload(
                "evaluator/derived.json",
                b"original",
                DataClass.PUBLIC_SYNTHETIC,
                (dependency,),
            ),
        ),
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    artifact = store.paths.evaluator_root / run_id / "derived.json"
    artifact.write_bytes(b"tampered")

    with pytest.raises(DataValidationError) as error:
        store.delete_source_closure(run_id, dependency)

    assert error.value.code == "persona_study_expiry_purge_incomplete"
    assert artifact.read_bytes() == b"tampered"


def test_study_cli_stdout_is_content_free_and_avoids_db_and_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root, sentinels = synthetic_codex_study_root(tmp_path)
    private_root = tmp_path / "private"

    source_reads: list[Path] = []

    def counted_source(
        root: Path, *, synthetic: bool, evaluation_time: datetime
    ) -> tuple[StudySourceSample, ProtectedHoldoutFreeze]:
        source_reads.append(root)
        return load_protected_study_source(
            root, synthetic=synthetic, evaluation_time=evaluation_time
        )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("database or model provider was called")

    monkeypatch.setattr("ynoy.persona_study.prepare.load_protected_study_source", counted_source)
    monkeypatch.setattr(CommandContext, "database", forbidden)
    monkeypatch.setattr(CommandContext, "setup_database", forbidden)
    monkeypatch.setattr("ynoy.reasoner.LocalOpenAIReasoner.__init__", forbidden)
    monkeypatch.setattr("ynoy.reasoner.DeterministicReasoner.complete", forbidden)

    exit_code = main(
        [
            "--indent",
            "0",
            "--private-root",
            str(private_root),
            "study",
            "prepare",
            str(source_root),
            "--synthetic",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    _assert_cli_study_result(
        exit_code, captured.out, captured.err, payload, sentinels, source_reads, private_root
    )


def _assert_cli_study_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    payload: dict[str, object],
    sentinels: tuple[str, ...],
    source_reads: list[Path],
    private_root: Path,
) -> None:
    assert exit_code == 0 and stderr == "" and payload["ok"] is True
    assert all(value not in stdout for value in sentinels)
    result = payload["result"]
    assert isinstance(result, dict)
    assert result["counts"]["unique_windows"] == 24
    assert result["counts"]["presentations"] == 32
    assert result["counts"]["blind_repeats"] == 8
    assert result["raw_content_emitted"] is False
    assert result["database_used"] is False
    assert result["model_provider_used"] is False
    assert result["automatic_core_promotion"] is False
    assert result["independent_source_replay_verified"] is True
    assert result["disposable_canary_deletion_proof"] == "passed"
    assert result["protected_holdout_claimed"] is True
    assert result["background_deletion_guaranteed"] is False
    assert len(source_reads) == 2
    assert "persona-study-annotator" in Path(result["review_path"]).parts
    evaluator = private_root / "persona-study-evaluator" / result["study_id"]
    assert (evaluator / "blind-map.json").is_file()
    assert not (Path(result["review_path"]).parent / "blind-map.json").exists()
