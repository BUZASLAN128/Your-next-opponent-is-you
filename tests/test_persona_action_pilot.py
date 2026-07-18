from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from support.harvest_authorship import (
    authorship_submission,
    prepare_authorship_fixture,
    replace_indexed_artifact,
)

from ynoy.errors import DataValidationError
from ynoy.models.harvest_authorship import seal_harvest_authorship_receipt
from ynoy.models.persona_action_pilot import (
    ActionPilotPrediction,
    ActionPilotTarget,
)
from ynoy.persona_study.action_pilot import (
    freeze_action_predictions,
    prepare_action_pilot,
    score_action_pilot,
)
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest_authorship import submit_harvest_authorship
from ynoy.util import canonical_json_bytes, canonical_sha256


def _prepared_pilot(tmp_path):
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    receipt = submit_harvest_authorship(store, authorship_submission(prepared)).receipt
    candidates = tuple(
        _reseal_candidate(item, now + timedelta(days=index + 1))
        for index, item in enumerate(prepared.checkpoint.candidates)
    )
    checkpoint_payload = prepared.checkpoint.model_dump(
        mode="python", exclude={"checkpoint_sha256"}
    )
    checkpoint_payload["candidates"] = candidates
    checkpoint_draft = type(prepared.checkpoint).model_construct(
        **checkpoint_payload, checkpoint_sha256="0" * 64
    )
    checkpoint_json = checkpoint_draft.model_dump(mode="json", exclude={"checkpoint_sha256"})
    checkpoint = type(prepared.checkpoint).model_validate(
        {
            **checkpoint_json,
            "checkpoint_sha256": canonical_sha256(checkpoint_json),
        }
    )
    candidate_hashes = tuple(item.candidate_sha256 for item in candidates)
    receipt_payload = receipt.model_dump(mode="python", exclude={"receipt_sha256"})
    receipt_payload["checkpoint_sha256"] = checkpoint.checkpoint_sha256
    receipt_payload["candidate_sha256s"] = candidate_hashes
    receipt_payload["candidate_set_sha256"] = canonical_sha256(
        {
            "candidate_ids": receipt.candidate_ids,
            "candidate_sha256s": candidate_hashes,
            "authorships": receipt.authorships,
        }
    )
    receipt = seal_harvest_authorship_receipt(**receipt_payload)
    prepared = replace(prepared, checkpoint=checkpoint)
    replace_indexed_artifact(
        store,
        prepared.manifest.run_id,
        f"evaluator/harvest-checkpoint-{checkpoint.cursor.revision:04d}.json",
        canonical_json_bytes(checkpoint.model_dump(mode="json")),
    )
    replace_indexed_artifact(
        store,
        prepared.manifest.run_id,
        f"evaluator/harvest-authorship-{receipt.revision:04d}.json",
        canonical_json_bytes(receipt.model_dump(mode="json")),
    )
    return prepared, receipt, prepare_action_pilot(checkpoint, receipt)


def _reseal_candidate(candidate, event_time):
    payload = candidate.model_dump(mode="python", exclude={"candidate_sha256"})
    payload["event_time"] = event_time
    draft = type(candidate).model_construct(**payload, candidate_sha256="0" * 64)
    payload = draft.model_dump(mode="json", exclude={"candidate_sha256"})
    return type(candidate).model_validate(
        {**payload, "candidate_sha256": canonical_sha256(payload)}
    )


def _predictions(manifest, arm: str, signal: str = "decision"):
    return tuple(
        ActionPilotPrediction(
            arm=arm,
            case_id=case_id,
            predicted_signal=signal,
            ranking_score=0.5,
            model="synthetic-deterministic",
        )
        for case_id in manifest.sealed_case_ids
    )


def _target(target: ActionPilotTarget, signal: str) -> ActionPilotTarget:
    payload = target.model_copy(update={"primary_signal": signal})
    return payload.model_copy(
        update={
            "target_sha256": canonical_sha256(
                payload.model_dump(mode="json", exclude={"target_sha256"})
            )
        }
    )


def test_prepare_action_pilot_binds_authorship_and_has_six_train_six_sealed(tmp_path) -> None:
    prepared, receipt, (manifest, history, cases, targets) = _prepared_pilot(tmp_path)

    assert manifest.source_study_id == prepared.manifest.source_study_id
    assert manifest.run_id == prepared.manifest.run_id
    assert manifest.authorship_receipt_sha256 == receipt.receipt_sha256
    assert manifest.checkpoint_sha256 == prepared.checkpoint.checkpoint_sha256
    assert len(history) == len(cases) == len(targets) == 6
    assert set(item.case_id for item in history) == set(manifest.history_case_ids)
    assert set(item.case_id for item in cases) == set(manifest.sealed_case_ids)
    assert max(item.event_time for item in history) < min(item.event_time for item in cases)
    assert manifest.target_visible_to_predictor is False
    assert manifest.persona_quality_claimed is False
    assert all(not hasattr(item, "focus") for item in cases)


def test_prepare_rejects_checkpoint_or_authorship_mismatch(tmp_path) -> None:
    prepared, receipt, _ = _prepared_pilot(tmp_path)
    changed = prepared.checkpoint.model_copy(update={"checkpoint_sha256": "f" * 64})
    with pytest.raises(DataValidationError):
        prepare_action_pilot(changed, receipt)

    foreign = receipt.model_copy(update={"checkpoint_sha256": "e" * 64})
    with pytest.raises(DataValidationError):
        prepare_action_pilot(prepared.checkpoint, foreign)


@pytest.mark.parametrize("kind", ["duplicate_source", "time_overlap"])
def test_prepare_fails_closed_on_source_or_time_leakage(tmp_path, kind: str) -> None:
    prepared, receipt, _ = _prepared_pilot(tmp_path)
    candidates = list(prepared.checkpoint.candidates)
    if kind == "duplicate_source":
        candidates[6] = candidates[6].model_copy(
            update={"source_receipt": candidates[0].source_receipt}
        )
    else:
        candidates[6] = candidates[6].model_copy(update={"event_time": candidates[5].event_time})
    tampered = prepared.checkpoint.model_copy(update={"candidates": tuple(candidates)})

    with pytest.raises(DataValidationError) as error:
        prepare_action_pilot(tampered, receipt)

    assert error.value.code in {"action_pilot_split_invalid", "action_pilot_authorship_mismatch"}


def test_prediction_freeze_is_target_free_and_requires_identical_case_sets(tmp_path) -> None:
    _, _, (manifest, history, _, targets) = _prepared_pilot(tmp_path)
    generic = _predictions(manifest, "generic")
    personalized = _predictions(manifest, "personalized", "correction")

    frozen = freeze_action_predictions(manifest, generic, personalized)
    assert frozen.targets_revealed is False
    assert frozen.manifest_sha256 == manifest.manifest_sha256
    assert all(item.target_seen is False for item in (*generic, *personalized))
    assert all(
        item.case_id not in item.model_dump(mode="json") for item in frozen.generic_predictions
    )

    replacement = "correction" if targets[0].primary_signal != "correction" else "decision"
    changed_targets = (_target(targets[0], replacement), *targets[1:])
    first = score_action_pilot(manifest, frozen, history, targets)
    second = score_action_pilot(manifest, frozen, history, changed_targets)
    assert frozen == freeze_action_predictions(manifest, generic, personalized)
    assert first.prediction_freeze_sha256 == second.prediction_freeze_sha256
    assert first.run_sha256 != second.run_sha256
    assert first.persona_quality_claimed is False

    swapped = (*tuple(personalized[1:]), personalized[0])
    with pytest.raises(DataValidationError):
        freeze_action_predictions(manifest, generic, swapped)


def test_signal_tie_order_is_stable_and_primary_signal_is_deterministic(tmp_path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    _, _, (first_manifest, first_history, _, _) = _prepared_pilot(first_root)
    _, _, (second_manifest, second_history, _, _) = _prepared_pilot(second_root)

    assert first_manifest.signal_tie_order == second_manifest.signal_tie_order
    assert tuple(item.primary_signal for item in first_history) == tuple(
        item.primary_signal for item in second_history
    )
    assert len(set(first_manifest.signal_tie_order)) == 6

    tie_root = tmp_path / "tie"
    tie_root.mkdir()
    prepared, receipt, _ = _prepared_pilot(tie_root)
    candidates = list(prepared.checkpoint.candidates)
    candidates[0] = candidates[0].model_copy(
        update={"signal_tags": ("outcome_feedback", "decision")}
    )
    _, history, _, _ = prepare_action_pilot(
        prepared.checkpoint.model_copy(update={"candidates": tuple(candidates)}), receipt
    )
    assert history[0].primary_signal == "decision"


def test_scoring_reports_only_directional_or_inconclusive_and_never_persona_quality(
    tmp_path,
) -> None:
    _, _, (manifest, history, _, targets) = _prepared_pilot(tmp_path)
    frozen = freeze_action_predictions(
        manifest,
        _predictions(manifest, "generic"),
        _predictions(manifest, "personalized"),
    )

    run = score_action_pilot(manifest, frozen, history, targets)

    assert run.status in {"positive_directional", "negative_directional", "inconclusive"}
    assert run.observable_action_only is True
    assert run.calibrated is False
    assert run.persona_quality_claimed is False
    assert run.automatic_core_promotion is False
    assert run.generic.case_count == run.personalized.case_count == 6


def test_personalized_tie_with_recent_history_baseline_is_inconclusive(tmp_path) -> None:
    _, _, (manifest, history, _, targets) = _prepared_pilot(tmp_path)
    recent_signal = history[-1].primary_signal
    tie_targets = (*targets[:2], *(_target(item, "scope_change") for item in targets[2:]))
    generic = list(_predictions(manifest, "generic", "correction"))
    personalized = list(_predictions(manifest, "personalized", "correction"))
    generic[0] = generic[0].model_copy(update={"predicted_signal": recent_signal})
    personalized[0] = personalized[0].model_copy(update={"predicted_signal": recent_signal})
    personalized[1] = personalized[1].model_copy(update={"predicted_signal": recent_signal})
    frozen = freeze_action_predictions(manifest, tuple(generic), tuple(personalized))

    run = score_action_pilot(manifest, frozen, history, tie_targets)

    assert run.personalized.correct_count == 2
    assert run.status == "inconclusive"
    assert "baseline" in run.reason.casefold() or "recent" in run.reason.casefold()


def test_target_receipts_are_separate_and_mutation_is_detected(tmp_path) -> None:
    _, _, (manifest, history, _, targets) = _prepared_pilot(tmp_path)
    tampered = targets[0].model_copy(update={"primary_signal": "abstention"})
    with pytest.raises(ValueError, match="target receipt"):
        type(targets[0]).model_validate(tampered.model_dump(mode="python"))

    frozen = freeze_action_predictions(
        manifest,
        _predictions(manifest, "generic"),
        _predictions(manifest, "personalized"),
    )
    with pytest.raises(DataValidationError):
        score_action_pilot(manifest, frozen, history, (*targets[1:], targets[0]))
