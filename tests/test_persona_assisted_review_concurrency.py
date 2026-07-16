from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier, Event

import pytest
from support.persona_assisted_review import ActiveReviewStudy, active_review_study

from ynoy.errors import DataValidationError
from ynoy.persona_study.assisted_review_submission import (
    ProposalReviewSubmission,
    record_proposal_review_decisions,
    submit_proposal_review,
)
from ynoy.persona_study.retention import ExpiryPurgeResult

REVIEW_PATH = "evaluator/model-proposal-review.json"
RECEIPT_PATH = "evaluator/model-proposal-review-receipt.json"


def _submit(study: ActiveReviewStudy) -> ProposalReviewSubmission | DataValidationError:
    try:
        return submit_proposal_review(study.store, study.study_id)
    except DataValidationError as exc:
        return exc


def test_concurrent_submissions_have_one_owner_and_one_fail_fast_loser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = active_review_study(tmp_path)
    record_proposal_review_decisions(
        study.store, study.study_id, confirm_orders=study.selected_orders()
    )
    rendezvous = Barrier(2)
    owner_acquired = Event()
    loser_finished = Event()
    original_lock = study.store.study_lock
    monkeypatch.setattr(
        study.store, "purge_expired", lambda _evaluation: ExpiryPurgeResult(0, 0, 0, 0)
    )

    @contextmanager
    def coordinated_lock(study_id: str) -> Iterator[None]:
        rendezvous.wait(timeout=10)
        try:
            with original_lock(study_id):
                owner_acquired.set()
                if not loser_finished.wait(timeout=10):
                    raise AssertionError("fail-fast lock contender did not finish")
                yield
        except DataValidationError as exc:
            if exc.code == "persona_study_locked":
                loser_finished.set()
            raise

    monkeypatch.setattr(study.store, "study_lock", coordinated_lock)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(
            item.result(timeout=20)
            for item in (pool.submit(_submit, study), pool.submit(_submit, study))
        )

    successes = tuple(item for item in outcomes if isinstance(item, ProposalReviewSubmission))
    failures = tuple(item for item in outcomes if isinstance(item, DataValidationError))
    assert owner_acquired.is_set() and loser_finished.is_set()
    assert len(successes) == len(failures) == 1
    assert failures[0].code == "persona_study_locked"
    index = study.store.read_index(study.study_id)
    paths = tuple(item.relative_path for item in index.entries)
    assert paths.count(REVIEW_PATH) == paths.count(RECEIPT_PATH) == 1
    draft = next(item for item in index.entries if item.relative_path == study.draft_path)
    assert draft.mutable_by == "none"
    replay = submit_proposal_review(study.store, study.study_id)
    assert replay.receipt == successes[0].receipt
    assert replay.artifact_index == index
