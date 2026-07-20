from __future__ import annotations

import pytest
from test_persona_reaction_benchmark import _dataset, _split

from ynoy.errors import DataValidationError
from ynoy.full_persona.reaction_scoring import (
    freeze_reaction_predictions,
    materialize_synthetic_reaction_targets,
    score_reaction_predictions,
)
from ynoy.models.persona_reaction_benchmark import (
    REACTION_ARMS,
    PersonaReactionArmPrediction,
)
from ynoy.models.persona_reaction_results import PersonaReactionTargetSet
from ynoy.util import canonical_sha256

_MODEL_BINDINGS = {
    "generic_local_8b": "local-8b@rev:artifact",
    "history_majority": "deterministic@v1",
    "chronological_recency": "deterministic@v1",
    "lexical_retrieval": "deterministic@v1",
    "static_profile": "deterministic@v1",
    "structured_persona": "local-8b@rev:artifact",
}


def _prediction(arm: str, case_id: str, label: str, *, score: float | None = 0.5):
    payload = {
        "arm": arm,
        "case_id": case_id,
        "predicted_label": label,
        "abstained": label == "abstain",
        "evidence_ids": (),
        "ranking_score": score,
        "target_seen": False,
        "target_text": None,
        "persona_identity": False,
        "calibration_used": False,
        "semantic_adoption": False,
        "core_eligible": False,
    }
    draft = PersonaReactionArmPrediction.model_construct(**payload, prediction_sha256="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"prediction_sha256"})
    return PersonaReactionArmPrediction.model_validate(
        {**normalized, "prediction_sha256": canonical_sha256(normalized)}
    )


def _predictions(split, label: str = "decision"):
    return {
        arm: tuple(_prediction(arm, case.case_id, label) for case in split.cases)
        for arm in REACTION_ARMS
    }


def _target_set(split, frozen) -> PersonaReactionTargetSet:
    return materialize_synthetic_reaction_targets(
        _dataset()[0], _dataset()[1], split.manifest, split.target_seal, frozen
    )


def _reseal_target_set(target_set: PersonaReactionTargetSet) -> PersonaReactionTargetSet:
    targets = []
    for item in target_set.targets:
        payload = item.model_dump(mode="json", exclude={"target_sha256"})
        payload["label"] = "decision" if item.label == "correction" else "correction"
        target_payload = {**payload, "target_sha256": canonical_sha256(payload)}
        targets.append(target_payload)
    payload = target_set.model_dump(mode="json", exclude={"target_set_sha256"})
    payload["targets"] = targets
    return PersonaReactionTargetSet.model_validate(
        {**payload, "target_set_sha256": canonical_sha256(payload)}
    )


def test_freeze_requires_six_arms_identical_case_order_and_bindings() -> None:
    split = _split()
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    assert frozen.manifest_sha256 == split.manifest.manifest_sha256
    assert frozen.target_seal_sha256 == split.target_seal.seal_sha256
    assert frozen.targets_revealed is False
    assert frozen.arms == REACTION_ARMS
    assert all(
        tuple(item.case_id for item in values) == split.manifest.sealed_case_ids
        for values in frozen.predictions.values()
    )
    assert frozen.model_bindings == _MODEL_BINDINGS


def test_freeze_rejects_missing_arm_or_reordered_predictions() -> None:
    split = _split()
    predictions = _predictions(split)
    with pytest.raises(DataValidationError):
        freeze_reaction_predictions(
            split.manifest,
            split.target_seal,
            cases=split.cases,
            predictions={
                key: value for key, value in predictions.items() if key != "structured_persona"
            },
            model_bindings=_MODEL_BINDINGS,
        )
    reordered = dict(predictions)
    reordered["generic_local_8b"] = tuple(reversed(reordered["generic_local_8b"]))
    with pytest.raises(DataValidationError):
        freeze_reaction_predictions(
            split.manifest,
            split.target_seal,
            cases=split.cases,
            predictions=reordered,
            model_bindings=_MODEL_BINDINGS,
        )


def test_targets_require_a_valid_prediction_freeze_and_remain_hash_only() -> None:
    split = _split()
    with pytest.raises(DataValidationError):
        materialize_synthetic_reaction_targets(
            _dataset()[0], _dataset()[1], split.manifest, split.target_seal, freeze=None
        )
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    targets = materialize_synthetic_reaction_targets(
        _dataset()[0], _dataset()[1], split.manifest, split.target_seal, frozen
    )
    assert len(targets.targets) == 24
    assert all("target_content" not in item.model_dump(mode="json") for item in targets.targets)
    assert all("target_text" not in item.model_dump(mode="json") for item in targets.targets)


def test_scoring_uses_zero_one_half_and_reports_inconclusive_support() -> None:
    split = _split()
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split, "abstain"),
        model_bindings=_MODEL_BINDINGS,
    )
    targets = _target_set(split, frozen)
    result = score_reaction_predictions(frozen, targets)
    assert result.cluster_count == split.manifest.sealed_cluster_count
    assert result.coverage["generic_local_8b"] == 0
    assert result.risk["generic_local_8b"] == 0.5
    assert result.status == "inconclusive"
    assert result.calibrated is False
    assert result.persona_quality_claimed is False


def test_scoring_loss_is_zero_correct_one_wrong_half_abstain() -> None:
    split = _split()
    frozen_for_targets = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    targets = _target_set(split, frozen_for_targets)
    predictions = _predictions(split)
    mixed = []
    for index, case in enumerate(split.cases):
        if index < 8:
            label = targets.targets[index].label
        elif index < 16:
            label = "decision" if targets.targets[index].label != "decision" else "correction"
        else:
            label = "abstain"
        mixed.append(_prediction("generic_local_8b", case.case_id, label))
    predictions["generic_local_8b"] = tuple(mixed)
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=predictions,
        model_bindings=_MODEL_BINDINGS,
    )
    targets = _target_set(split, frozen)
    result = score_reaction_predictions(frozen, targets)
    assert result.coverage["generic_local_8b"] == 16 / 24
    assert result.risk["generic_local_8b"] == 0.5


def test_hidden_target_mutation_cannot_change_frozen_predictions() -> None:
    split = _split()
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    original = _target_set(split, frozen)
    stale = original.model_copy(
        update={
            "targets": tuple(
                item.model_copy(update={"label": "decision"}) for item in original.targets
            )
        }
    )
    with pytest.raises(DataValidationError):
        score_reaction_predictions(frozen, stale)
    with pytest.raises(DataValidationError):
        score_reaction_predictions(frozen, original.targets)
    changed = _reseal_target_set(original)
    assert frozen == freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    assert score_reaction_predictions(frozen, original) != score_reaction_predictions(
        frozen, changed
    )


def test_matched_support_and_cluster_binding_are_frozen() -> None:
    split = _split()
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    assert frozen.matched_case_ids == split.manifest.sealed_case_ids[:18]
    assert tuple(frozen.case_clusters) == split.manifest.sealed_case_ids
    targets = _target_set(split, frozen)
    result = score_reaction_predictions(frozen, targets)
    assert result.matched_case_count == 18
    assert result.matched_cluster_count == len(
        {frozen.case_clusters[item] for item in frozen.matched_case_ids}
    )


def test_different_arm_coverage_cannot_produce_positive_directional() -> None:
    split = _split()
    predictions = _predictions(split, "decision")
    predictions["structured_persona"] = tuple(
        _prediction("structured_persona", case.case_id, "correction") for case in split.cases
    )
    generic = list(predictions["generic_local_8b"])
    generic[0] = _prediction("generic_local_8b", split.cases[0].case_id, "abstain")
    predictions["generic_local_8b"] = tuple(generic)
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=predictions,
        model_bindings=_MODEL_BINDINGS,
    )
    result = score_reaction_predictions(frozen, _target_set(split, frozen))
    assert result.status == "inconclusive"
