from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from support.harvest_authorship import authorship_submission, prepare_authorship_fixture

from ynoy.cli.context import CommandContext
from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest_authorship import submit_harvest_authorship


def test_all_self_authorship_submission_seals_private_receipt(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)

    assert len(prepared.checkpoint.candidates) == 12
    assert prepared.checkpoint.status in {"audit_ready", "complete"}

    result = submit_harvest_authorship(store, authorship_submission(prepared))

    assert result.receipt.run_id == prepared.manifest.run_id
    assert result.receipt.source_study_id == prepared.manifest.source_study_id
    assert result.receipt.revision == prepared.checkpoint.cursor.revision
    assert result.receipt.candidate_ids == tuple(
        item.candidate_id for item in prepared.checkpoint.candidates
    )
    assert result.receipt.authorships == ("self",) * len(result.receipt.candidate_ids)
    assert result.receipt.judgment_signal is None
    assert result.receipt.adoption is None
    assert result.receipt.core_eligible is False
    assert result.receipt.benchmark_eligible is False
    assert any("authorship" in entry.relative_path for entry in result.artifact_index.entries)


def test_exact_authorship_retry_is_idempotent(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    submission = authorship_submission(prepared)

    first = submit_harvest_authorship(store, submission)
    second = submit_harvest_authorship(store, submission)

    assert second.receipt == first.receipt
    assert second.artifact_index == first.artifact_index


def test_changed_authorship_retry_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    first = submit_harvest_authorship(store, authorship_submission(prepared))
    changed_values = ("other",) + ("self",) * (len(first.receipt.candidate_ids) - 1)

    with pytest.raises(DataValidationError):
        submit_harvest_authorship(
            store, authorship_submission(prepared, authorships=changed_values)
        )


def test_tampered_authorship_receipt_fails_closed(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    result = submit_harvest_authorship(store, authorship_submission(prepared))
    path = next(
        store.paths.artifact(prepared.manifest.run_id, entry.relative_path)
        for entry in result.artifact_index.entries
        if "authorship" in entry.relative_path
    )
    path.write_bytes(b"tampered")

    with pytest.raises(DataValidationError) as error:
        submit_harvest_authorship(store, authorship_submission(prepared))

    assert error.value.code in {
        "persona_study_artifact_tampered",
        "persona_study_index_invalid",
        "persona_study_expiry_purge_incomplete",
    }


def test_authorship_receipt_is_deleted_by_retention_purge(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    result = submit_harvest_authorship(store, authorship_submission(prepared))
    expired = PersonaStudyStore(private, real_data=False, evaluation_time=now + timedelta(days=8))

    purge = expired.purge_expired(now + timedelta(days=8))

    assert purge.deleted_artifact_count >= len(result.artifact_index.entries)
    with pytest.raises(DataValidationError):
        expired.read_index(prepared.manifest.run_id)


def test_source_dependency_deletion_removes_authorship_closure(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    result = submit_harvest_authorship(store, authorship_submission(prepared))
    receipt_entry = next(
        entry for entry in result.artifact_index.entries if "authorship" in entry.relative_path
    )

    deleted = store.delete_source_closure(
        prepared.manifest.run_id, receipt_entry.source_dependencies[0]
    )

    assert deleted >= 1
    try:
        index = store.read_index(prepared.manifest.run_id)
    except DataValidationError:
        return
    assert not any("authorship" in entry.relative_path for entry in index.entries)


def test_cli_authorship_seal_is_local_and_emits_safe_summary(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _, private, prepared, _ = prepare_authorship_fixture(tmp_path)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("authorship CLI must not call database or model provider")

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
            "seal-harvest-authorship",
            prepared.manifest.run_id,
            "--revision",
            str(prepared.checkpoint.cursor.revision),
            "--checkpoint-sha256",
            prepared.checkpoint.checkpoint_sha256,
            "--confirm-all-self",
            "--synthetic",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    result = payload["result"]

    assert code == 0 and payload["ok"] is True
    assert result["status"] == "harvest_authorship_sealed_not_judgment"
    assert result["confirmed_authorship_count"] == 12
    assert result["private_content_emitted"] is False
    assert result["database_used"] is False
    assert result["model_provider_used"] is False
    assert result["automatic_core_promotion"] is False
    assert result["persona_quality_claimed"] is False
    assert all(item.focus not in captured.out for item in prepared.checkpoint.candidates)
    assert all(item.candidate_id not in captured.out for item in prepared.checkpoint.candidates)
