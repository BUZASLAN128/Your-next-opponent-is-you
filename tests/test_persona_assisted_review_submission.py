from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.persona_assisted_review import (
    ActiveReviewStudy,
    active_review_study,
    corrected_judgment,
)

from ynoy.errors import DataValidationError
from ynoy.models import DataClass
from ynoy.persona_study import artifacts as artifact_module
from ynoy.persona_study.assisted_review_submission import (
    record_proposal_review_decisions,
    submit_proposal_review,
)

PRIMARY_REVIEW = "evaluator/model-proposal-review.json"
PRIMARY_RECEIPT = "evaluator/model-proposal-review-receipt.json"
RETRY_REVIEW = "evaluator/model-proposal-review.retry-01.json"
RETRY_RECEIPT = "evaluator/model-proposal-review-receipt.retry-01.json"


def _record_all(study: ActiveReviewStudy, *, not_mine: bool = False) -> tuple[int, ...]:
    orders = study.selected_orders()
    excluded = orders[:1] if not_mine else ()
    confirmed = orders[1:] if not_mine else orders
    result = record_proposal_review_decisions(
        study.store,
        study.study_id,
        confirm_orders=confirmed,
        not_mine_orders=excluded,
    )
    assert result.decided_count == result.selected_count
    assert result.pending_count == result.correction_pending_count == 0
    return orders


def _artifact_paths(study: ActiveReviewStudy) -> tuple[str, str]:
    return (
        (RETRY_REVIEW, RETRY_RECEIPT)
        if "retry-01" in study.draft_path
        else (
            PRIMARY_REVIEW,
            PRIMARY_RECEIPT,
        )
    )


def _write_draft(study: ActiveReviewStudy, value: dict[str, object]) -> None:
    path = study.store.paths.artifact(study.study_id, study.draft_path)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_submission_seals_review_with_conservative_not_mine_and_replays(
    tmp_path: Path,
) -> None:
    study = active_review_study(tmp_path)
    orders = _record_all(study, not_mine=True)

    first = submit_proposal_review(study.store, study.study_id)
    review_path, receipt_path = _artifact_paths(study)
    index = study.store.read_index(study.study_id)
    entries = {item.relative_path: item for item in index.entries}

    assert first.attempt == "primary"
    assert first.review.schema_version == "persona-proposal-review-sealed/0.1"
    assert first.receipt.schema_version == "persona-proposal-review-receipt/0.1"
    assert first.receipt.reviewed_count == len(orders)
    assert first.receipt.not_mine_count == 1
    assert first.receipt.confirm_count == len(orders) - 1
    assert first.receipt.confirmed_proposal_count == len(orders) - 1
    assert entries[study.draft_path].mutable_by == "none"
    assert entries[review_path].mutable_by == entries[receipt_path].mutable_by == "none"
    not_mine = next(item for item in first.review.decisions if item.action == "not_mine")
    final = not_mine.final_judgment
    assert final.authorship == "other" and final.claim_holder == "unknown"
    assert final.adoption == final.decision == final.target_layer == "unknown"
    assert final.should_abstain and final.exclude_from_persona
    assert final.exclusion_reason == "not_mine" and final.confidence == "high"
    assert final.rationale_spans[0].text == study.focus(not_mine.order)
    assert not not_mine.core_eligible and not not_mine.automatic_core_promotion
    assert not first.receipt.persona_quality_claimed
    assert not first.receipt.protected_holdout_used
    assert not first.receipt.automatic_core_promotion

    replay = submit_proposal_review(study.store, study.study_id)
    assert replay.receipt == first.receipt
    assert replay.artifact_index == index
    with pytest.raises(DataValidationError) as blocked:
        record_proposal_review_decisions(study.store, study.study_id, confirm_orders=(orders[0],))
    assert blocked.value.code == "persona_proposal_review_already_sealed"


def test_retry_submission_uses_retry_artifacts(tmp_path: Path) -> None:
    study = active_review_study(tmp_path, retry=True)
    _record_all(study)

    result = submit_proposal_review(study.store, study.study_id)

    assert result.attempt == "retry_01"
    paths = {item.relative_path for item in result.artifact_index.entries}
    assert RETRY_REVIEW in paths and RETRY_RECEIPT in paths
    assert PRIMARY_REVIEW not in paths and PRIMARY_RECEIPT not in paths


def test_incomplete_and_correction_pending_reviews_cannot_submit(tmp_path: Path) -> None:
    study = active_review_study(tmp_path)
    first, second, *_ = study.selected_orders()
    record_proposal_review_decisions(
        study.store,
        study.study_id,
        confirm_orders=(first,),
        correct_orders=(second,),
    )

    with pytest.raises(DataValidationError) as blocked:
        submit_proposal_review(study.store, study.study_id)

    assert blocked.value.code == "persona_proposal_review_incomplete"
    paths = {item.relative_path for item in study.store.read_index(study.study_id).entries}
    assert PRIMARY_REVIEW not in paths and PRIMARY_RECEIPT not in paths


def test_submission_rejects_template_binding_tamper_without_sealing(tmp_path: Path) -> None:
    study = active_review_study(tmp_path)
    _record_all(study)
    draft = study.draft()
    draft["proposal_receipt_sha256"] = "0" * 64
    _write_draft(study, draft)

    with pytest.raises(DataValidationError) as blocked:
        submit_proposal_review(study.store, study.study_id)

    assert blocked.value.code == "persona_proposal_review_contract_changed"
    entry = next(
        item
        for item in study.store.read_index(study.study_id).entries
        if item.relative_path == study.draft_path
    )
    assert entry.mutable_by == "represented_user"


def test_corrected_judgment_requires_exact_focus_span(tmp_path: Path) -> None:
    study = active_review_study(tmp_path)
    target, *remaining = study.selected_orders()
    record_proposal_review_decisions(
        study.store,
        study.study_id,
        confirm_orders=tuple(remaining),
        correct_orders=(target,),
    )
    draft = study.draft()
    action = next(item for item in draft["actions"] if item["order"] == target)
    corrected = corrected_judgment(study, target).model_dump(mode="json")
    corrected["rationale_spans"] = [{"start": 0, "end": 1, "text": "!"}]
    action["corrected_judgment"] = corrected
    draft["completed_by"] = "represented_user"
    _write_draft(study, draft)

    with pytest.raises(DataValidationError) as blocked:
        submit_proposal_review(study.store, study.study_id)

    assert blocked.value.code == "persona_label_span_mismatch"
    assert not study.store.paths.artifact(study.study_id, PRIMARY_REVIEW).exists()


def test_completed_private_correction_can_be_sealed(tmp_path: Path) -> None:
    study = active_review_study(tmp_path)
    target, *remaining = study.selected_orders()
    record_proposal_review_decisions(
        study.store,
        study.study_id,
        confirm_orders=tuple(remaining),
        correct_orders=(target,),
    )
    draft = study.draft()
    action = next(item for item in draft["actions"] if item["order"] == target)
    corrected = corrected_judgment(study, target)
    action["corrected_judgment"] = corrected.model_dump(mode="json")
    draft["completed_by"] = "represented_user"
    _write_draft(study, draft)

    result = submit_proposal_review(study.store, study.study_id)

    sealed = next(item for item in result.review.decisions if item.order == target)
    assert sealed.action == "correct" and sealed.final_judgment == corrected
    assert result.receipt.correct_count == 1
    assert result.receipt.confirm_count == len(remaining)


def test_submission_detects_stale_draft_before_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = active_review_study(tmp_path)
    _record_all(study)
    from ynoy.persona_study import assisted_review_submission as submission_module

    original = submission_module.replace_and_seal_mutable_locked

    def mutate_then_seal(*args: object, **kwargs: object) -> object:
        path = study.store.paths.artifact(study.study_id, study.draft_path)
        path.write_bytes(path.read_bytes() + b" ")
        return original(*args, **kwargs)

    monkeypatch.setattr(submission_module, "replace_and_seal_mutable_locked", mutate_then_seal)
    with pytest.raises(DataValidationError) as blocked:
        submit_proposal_review(study.store, study.study_id)

    assert blocked.value.code == "persona_study_mutable_changed"
    assert not study.store.paths.artifact(study.study_id, PRIMARY_REVIEW).exists()


def test_submission_write_failure_rolls_back_and_keeps_draft_mutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    study = active_review_study(tmp_path)
    _record_all(study)
    before = study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True)
    original_write = artifact_module.exclusive_write_bytes
    calls = 0

    def fail_second(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected review receipt failure")
        original_write(path, content)

    monkeypatch.setattr(artifact_module, "exclusive_write_bytes", fail_second)
    with pytest.raises(OSError, match="injected review receipt failure"):
        submit_proposal_review(study.store, study.study_id)

    index = study.store.read_index(study.study_id)
    draft = next(item for item in index.entries if item.relative_path == study.draft_path)
    assert draft.mutable_by == "represented_user"
    assert (
        study.store.read_artifact(study.study_id, study.draft_path, allow_user_draft=True) == before
    )
    assert not study.store.paths.artifact(study.study_id, PRIMARY_REVIEW).exists()
    assert not study.store.paths.artifact(study.study_id, PRIMARY_RECEIPT).exists()


def test_real_shaped_review_uses_d2_and_receipt_uses_d3(tmp_path: Path) -> None:
    study = active_review_study(tmp_path, real_shaped=True)
    _record_all(study)

    result = submit_proposal_review(study.store, study.study_id)
    entries = {item.relative_path: item for item in result.artifact_index.entries}

    assert entries[PRIMARY_REVIEW].data_class == DataClass.RAW_CORPUS
    assert entries[PRIMARY_RECEIPT].data_class == DataClass.DERIVED_IDENTITY
