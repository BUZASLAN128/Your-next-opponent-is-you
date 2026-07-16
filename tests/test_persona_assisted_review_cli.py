from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.persona_assisted_review import ActiveReviewStudy, active_review_study

from ynoy.cli.main import main
from ynoy.persona_study import assisted_labels as assisted_module

RECEIPT_PATH = "evaluator/model-proposal-review-receipt.json"


def _record_args(study: ActiveReviewStudy, orders: tuple[int, ...]) -> list[str]:
    return [
        "--indent",
        "0",
        "--private-root",
        str(study.store.root),
        "study",
        "record-proposal-review",
        study.study_id,
        "--synthetic",
        "--not-mine",
        str(orders[0]),
        "--confirm",
        ",".join(str(item) for item in orders[1:]),
    ]


def _submit_args(study: ActiveReviewStudy) -> list[str]:
    return [
        "--indent",
        "0",
        "--private-root",
        str(study.store.root),
        "study",
        "submit-proposal-review",
        study.study_id,
        "--synthetic",
    ]


def test_review_cli_emits_only_aggregate_lifecycle_status(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    study = active_review_study(tmp_path, evaluation_time=datetime.now(UTC))
    orders = study.selected_orders()
    private_focus = assisted_module.presentations(study.store, study.study_id)[0].focus.content
    proposal_receipt = study.draft()["proposal_receipt_sha256"]

    record_exit = main(_record_args(study, orders))
    record_output = capsys.readouterr().out
    record = json.loads(record_output)

    assert record_exit == 0
    assert record["result"]["status"] == "proposal_review_ready_to_submit"
    assert record["result"]["private_content_emitted"] is False
    assert private_focus not in record_output and study.study_id not in record_output
    assert proposal_receipt not in record_output

    submit_exit = main(_submit_args(study))
    submit_output = capsys.readouterr().out
    submit = json.loads(submit_output)
    receipt = json.loads(study.store.read_artifact(study.study_id, RECEIPT_PATH))

    assert submit_exit == 0
    assert submit["result"]["status"] == "proposal_review_sealed_not_persona_quality"
    assert submit["result"]["private_content_emitted"] is False
    assert submit["result"]["persona_quality_claimed"] is False
    assert submit["result"]["protected_holdout_used"] is False
    assert submit["result"]["automatic_core_promotion"] is False
    assert private_focus not in submit_output and study.study_id not in submit_output
    assert receipt["receipt_sha256"] not in submit_output
