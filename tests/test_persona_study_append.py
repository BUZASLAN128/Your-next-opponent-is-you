from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.models import DataClass, StudyArtifactEntry
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.util import canonical_sha256

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _simple_run(root: Path) -> tuple[PersonaStudyStore, str]:
    store = PersonaStudyStore(root, real_data=False, evaluation_time=_NOW)
    study_id = canonical_sha256((str(root), "append-study"))
    store.write_run(
        study_id,
        (
            ArtifactPayload(
                "evaluator/indexed.json",
                b"{}",
                DataClass.PUBLIC_SYNTHETIC,
                (canonical_sha256((study_id, "source")),),
            ),
        ),
        created_at=_NOW,
        expires_at=_NOW + timedelta(days=7),
    )
    return store, study_id


def test_append_preserves_existing_entries_and_declares_mutable_review(tmp_path: Path) -> None:
    store, study_id = _simple_run(tmp_path / "private")
    before = store.read_index(study_id)
    dependency = canonical_sha256((study_id, "assisted-label-proposal"))

    updated = store.append_artifacts(
        study_id,
        (
            ArtifactPayload(
                "evaluator/model-proposals.json",
                b'{"proposal_only":true}',
                DataClass.PUBLIC_SYNTHETIC,
                (dependency,),
            ),
            ArtifactPayload(
                "annotator/quick-review.template.json",
                b'{"completed_by":null}',
                DataClass.PUBLIC_SYNTHETIC,
                (dependency,),
                "represented_user",
            ),
        ),
    )

    assert updated.created_at == before.created_at and updated.expires_at == before.expires_at
    assert updated.entries[: len(before.entries)] == before.entries
    immutable = updated.entries[-2]
    mutable = updated.entries[-1]
    assert immutable.mutable_by == "none"
    assert mutable.mutable_by == "represented_user"
    assert store.read_artifact(study_id, immutable.relative_path) == b'{"proposal_only":true}'
    with pytest.raises(DataValidationError) as denied:
        store.read_artifact(study_id, mutable.relative_path)
    assert denied.value.code == "persona_study_mutable_read_denied"


def test_append_rolls_back_new_files_when_index_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id = _simple_run(tmp_path / "private")
    before = store.read_index(study_id)
    target = "evaluator/append-rollback.json"

    def fail_index_write(_: object) -> None:
        raise OSError("injected append index failure")

    monkeypatch.setattr(store, "_write_index", fail_index_write)
    with pytest.raises(OSError, match="injected append index failure"):
        store.append_artifacts(
            study_id,
            (
                ArtifactPayload(
                    target,
                    b"{}",
                    DataClass.PUBLIC_SYNTHETIC,
                    (canonical_sha256((study_id, target)),),
                ),
            ),
        )

    assert not store.paths.artifact(study_id, target).exists()
    assert store.read_index(study_id) == before


def test_append_refuses_to_replace_an_existing_artifact(tmp_path: Path) -> None:
    store, study_id = _simple_run(tmp_path / "private")
    before = store.read_index(study_id)
    existing = before.entries[0]

    with pytest.raises(DataValidationError) as blocked:
        store.append_artifacts(
            study_id,
            (
                ArtifactPayload(
                    existing.relative_path,
                    b'{"replacement":true}',
                    DataClass.PUBLIC_SYNTHETIC,
                    existing.source_dependencies,
                ),
            ),
        )

    assert blocked.value.code == "persona_study_artifact_exists"
    assert store.read_index(study_id) == before
    assert store.read_artifact(study_id, existing.relative_path) == b"{}"


def test_append_restores_index_before_cleanup_after_post_commit_verification_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id = _simple_run(tmp_path / "private")
    before = store.read_index(study_id)
    target = "evaluator/post-commit-rollback.json"
    original_verify = store._verify_entries

    def fail_post_commit_verify(target_study: str, entries: tuple[StudyArtifactEntry, ...]) -> None:
        if any(entry.relative_path == target for entry in entries):
            raise OSError("injected post-commit verification failure")
        original_verify(target_study, entries)

    monkeypatch.setattr(store, "_verify_entries", fail_post_commit_verify)
    with pytest.raises(OSError, match="injected post-commit verification failure"):
        store.append_artifacts(
            study_id,
            (
                ArtifactPayload(
                    target,
                    b"{}",
                    DataClass.PUBLIC_SYNTHETIC,
                    (canonical_sha256((study_id, target)),),
                ),
            ),
        )

    assert not store.paths.artifact(study_id, target).exists()
    assert store.read_index(study_id) == before


def test_append_preserves_committed_payload_when_index_rollback_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id = _simple_run(tmp_path / "private")
    target = "evaluator/incomplete-rollback.json"
    original_verify = store._verify_entries
    original_write = store._write_index
    write_calls = 0

    def fail_post_commit_verify(target_study: str, entries: tuple[StudyArtifactEntry, ...]) -> None:
        if any(entry.relative_path == target for entry in entries):
            raise OSError("injected verification failure")
        original_verify(target_study, entries)

    def fail_rollback(index: object) -> None:
        nonlocal write_calls
        write_calls += 1
        if write_calls == 2:
            raise OSError("injected rollback write failure")
        original_write(index)

    monkeypatch.setattr(store, "_verify_entries", fail_post_commit_verify)
    monkeypatch.setattr(store, "_write_index", fail_rollback)
    with pytest.raises(DataValidationError) as blocked:
        store.append_artifacts(
            study_id,
            (
                ArtifactPayload(
                    target,
                    b"{}",
                    DataClass.PUBLIC_SYNTHETIC,
                    (canonical_sha256((study_id, target)),),
                ),
            ),
        )

    assert blocked.value.code == "persona_study_rollback_incomplete"
    monkeypatch.undo()
    assert store.paths.artifact(study_id, target).exists()
    assert any(entry.relative_path == target for entry in store.read_index(study_id).entries)
