from __future__ import annotations

from pathlib import Path

import pytest
from support.persona_assisted_review import active_review_study, forge_selected_focus_mismatch

from ynoy.errors import DataValidationError
from ynoy.persona_study.assisted_review_submission import (
    record_proposal_review_decisions,
)


def test_record_decisions_is_partial_resumable_and_idempotent(tmp_path: Path) -> None:
    study = active_review_study(tmp_path)
    first, second, *remaining = study.selected_orders()

    partial = record_proposal_review_decisions(study.store, study.study_id, confirm_orders=(first,))
    resumed = record_proposal_review_decisions(
        study.store, study.study_id, not_mine_orders=(second,)
    )
    before_replay = study.store.read_artifact(
        study.study_id, study.draft_path, allow_user_draft=True
    )
    replay = record_proposal_review_decisions(study.store, study.study_id, confirm_orders=(first,))

    assert partial.attempt == resumed.attempt == replay.attempt == "primary"
    assert partial.selected_count == 8 and partial.decided_count == 1
    assert resumed.decided_count == replay.decided_count == 2
    assert resumed.pending_count == replay.pending_count == len(remaining)
    assert replay.correction_pending_count == 0
    assert (
        study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True)
        == before_replay
    )


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("duplicate", "persona_proposal_review_decision_conflict"),
        ("conflict", "persona_proposal_review_decision_conflict"),
        ("unknown", "persona_proposal_review_card_unknown"),
    ],
)
def test_invalid_order_sets_fail_before_mutating_draft(
    tmp_path: Path, case: str, code: str
) -> None:
    study = active_review_study(tmp_path)
    selected = study.selected_orders()
    unknown = next(order for order in range(1, 33) if order not in selected)
    before = study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True)
    kwargs = {
        "duplicate": {"confirm_orders": (selected[0], selected[0])},
        "conflict": {
            "confirm_orders": (selected[0],),
            "not_mine_orders": (selected[0],),
        },
        "unknown": {"confirm_orders": (unknown,)},
    }[case]

    with pytest.raises(DataValidationError) as blocked:
        record_proposal_review_decisions(study.store, study.study_id, **kwargs)

    assert blocked.value.code == code
    assert (
        study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True) == before
    )


def test_confirm_is_unavailable_without_a_chosen_proposal(tmp_path: Path) -> None:
    study = active_review_study(tmp_path, unconfirmable=True)
    action = next(item for item in study.draft()["actions"] if item["proposed_judgment"] is None)
    before = study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True)

    with pytest.raises(DataValidationError) as blocked:
        record_proposal_review_decisions(
            study.store, study.study_id, confirm_orders=(action["order"],)
        )

    assert blocked.value.code == "persona_proposal_review_confirm_unavailable"
    assert (
        study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True) == before
    )


def test_correct_decision_stays_pending_until_private_judgment_is_filled(
    tmp_path: Path,
) -> None:
    study = active_review_study(tmp_path)
    target = study.selected_orders()[0]

    result = record_proposal_review_decisions(study.store, study.study_id, correct_orders=(target,))

    action = next(item for item in study.draft()["actions"] if item["order"] == target)
    assert action["action"] == "correct"
    assert action["corrected_judgment"] is None
    assert result.decided_count == 0
    assert result.correction_pending_count == 1
    assert result.pending_count == result.selected_count


def test_retry_review_is_selected_automatically(tmp_path: Path) -> None:
    study = active_review_study(tmp_path, retry=True)
    target = study.selected_orders()[0]

    result = record_proposal_review_decisions(
        study.store, study.study_id, not_mine_orders=(target,)
    )

    assert result.attempt == "retry_01"
    action = next(item for item in study.draft()["actions"] if item["order"] == target)
    assert action["action"] == "not_mine"


def test_empty_record_and_conflicting_redecision_fail_closed(tmp_path: Path) -> None:
    study = active_review_study(tmp_path)
    target = study.selected_orders()[0]
    with pytest.raises(DataValidationError) as empty:
        record_proposal_review_decisions(study.store, study.study_id)
    assert empty.value.code == "persona_proposal_review_decision_required"
    record_proposal_review_decisions(study.store, study.study_id, confirm_orders=(target,))
    before = study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True)

    with pytest.raises(DataValidationError) as conflict:
        record_proposal_review_decisions(study.store, study.study_id, not_mine_orders=(target,))

    assert conflict.value.code == "persona_proposal_review_decision_already_recorded"
    assert (
        study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True) == before
    )


def test_record_rejects_rehashed_proposal_with_wrong_focus_binding(
    tmp_path: Path,
) -> None:
    study = active_review_study(tmp_path)
    target = study.selected_orders()[0]
    forge_selected_focus_mismatch(study)
    before = study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True)

    with pytest.raises(DataValidationError) as blocked:
        record_proposal_review_decisions(study.store, study.study_id, confirm_orders=(target,))

    assert blocked.value.code == "persona_proposal_review_contract_changed"
    assert (
        study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True) == before
    )
