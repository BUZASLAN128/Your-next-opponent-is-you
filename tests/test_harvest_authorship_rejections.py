from __future__ import annotations

from pathlib import Path

import pytest
from support.harvest_authorship import authorship_submission, prepare_authorship_fixture
from ynoy.persona_study.harvest_authorship import submit_harvest_authorship

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models.persona_harvest import HarvestLimits
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest import prepare_harvest, resume_harvest


def _reject(private: Path, now, submission) -> None:
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    with pytest.raises(DataValidationError):
        submit_harvest_authorship(store, submission)


def test_changed_checkpoint_is_rejected(tmp_path: Path) -> None:
    source, private, prepared, now = prepare_authorship_fixture(tmp_path)
    _ = source
    submission = authorship_submission(prepared, checkpoint_sha256="a" * 64)

    _reject(private, now, submission)


def test_wrong_revision_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    submission = authorship_submission(prepared, revision=prepared.checkpoint.cursor.revision + 1)

    _reject(private, now, submission)


def test_stale_revision_after_resume_is_rejected(tmp_path: Path) -> None:
    source, private, prepared, now = prepare_authorship_fixture(tmp_path)
    resumed = resume_harvest(source, private, prepared.manifest.run_id, synthetic=True)
    assert resumed.checkpoint.cursor.revision > prepared.checkpoint.cursor.revision

    _reject(private, now, authorship_submission(prepared))


def test_cross_run_submission_is_rejected(tmp_path: Path) -> None:
    source, private, prepared, now = prepare_authorship_fixture(tmp_path)
    second = prepare_harvest(
        source,
        private,
        prepared.manifest.source_study_id,
        synthetic=True,
        limits=HarvestLimits(max_files=4, max_entries=256),
        evaluation_time=now,
    )

    _reject(private, now, authorship_submission(prepared, run_id=second.manifest.run_id))


def test_wrong_source_study_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)

    _reject(private, now, authorship_submission(prepared, source_study_id="4" * 64))


def test_wrong_candidate_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    ids = tuple(
        "f" * 64 if index == 0 else item.candidate_id
        for index, item in enumerate(prepared.checkpoint.candidates)
    )

    _reject(private, now, authorship_submission(prepared, candidate_ids=ids))


def test_duplicate_candidate_ids_are_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    first = prepared.checkpoint.candidates[0].candidate_id
    ids = (first,) * len(prepared.checkpoint.candidates)

    _reject(private, now, authorship_submission(prepared, candidate_ids=ids))


def test_extra_candidate_id_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    ids = (*tuple(item.candidate_id for item in prepared.checkpoint.candidates), "e" * 64)

    _reject(private, now, authorship_submission(prepared, candidate_ids=ids))


def test_partial_candidate_set_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    ids = tuple(item.candidate_id for item in prepared.checkpoint.candidates[:-1])

    _reject(private, now, authorship_submission(prepared, candidate_ids=ids))


def test_mixed_authorship_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    values = ("self", "other")

    _reject(private, now, authorship_submission(prepared, authorships=values))


def test_candidate_order_change_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    ids = tuple(item.candidate_id for item in reversed(prepared.checkpoint.candidates))

    _reject(private, now, authorship_submission(prepared, candidate_ids=ids))


def test_private_root_inside_git_worktree_is_rejected() -> None:
    with pytest.raises(PolicyViolation) as error:
        PersonaStudyStore(Path(__file__).resolve().parents[1], real_data=True)

    assert error.value.code == "private_root_inside_git"
