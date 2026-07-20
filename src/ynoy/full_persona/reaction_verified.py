from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ynoy.errors import AdapterError, DataValidationError
from ynoy.full_persona.local_model_artifact import verify_local_model_artifact
from ynoy.full_persona.reaction_baselines import run_reaction_baselines
from ynoy.full_persona.reaction_contracts import seal_model
from ynoy.full_persona.reaction_model import LocalReactionModelAdapter, ModelReactionArm
from ynoy.full_persona.reaction_model_protocol import (
    DECODE_SETTINGS,
    ReactionModelCandidate,
    build_reaction_request,
    parse_reaction_envelope,
    select_reaction_history,
)
from ynoy.full_persona.reaction_profile import (
    ReactionDevelopmentProfile,
    build_reaction_profile,
)
from ynoy.full_persona.reaction_score_runtime import score_reaction_predictions
from ynoy.full_persona.reaction_split import ReactionSplit, build_verified_reaction_split
from ynoy.full_persona.reaction_targets import materialize_reaction_targets
from ynoy.full_persona.store import FullPersonaStore
from ynoy.local_http import post_json
from ynoy.models.full_persona import FullCorpusHead, FullCorpusManifest
from ynoy.models.persona_reaction_benchmark import (
    REACTION_ARMS,
    PersonaReactionArmPrediction,
    PersonaReactionBaselineRun,
    PersonaReactionCase,
    PersonaReactionHistory,
    ReactionArm,
)
from ynoy.models.persona_reaction_results import (
    PersonaReactionComparisonResult,
    PersonaReactionModelRun,
    PersonaReactionPredictionFreeze,
    PersonaReactionTargetSet,
)
from ynoy.util import canonical_sha256

_MAX_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class VerifiedReactionBenchmark:
    baseline_run: PersonaReactionBaselineRun
    model_run: PersonaReactionModelRun
    prediction_freeze: PersonaReactionPredictionFreeze
    target_set: PersonaReactionTargetSet
    result: PersonaReactionComparisonResult


def run_verified_reaction_benchmark(
    adapter: LocalReactionModelAdapter,
    store: FullPersonaStore,
    source_manifest: FullCorpusManifest,
    source_head: FullCorpusHead,
) -> VerifiedReactionBenchmark:
    """Rebuild and execute the complete private benchmark without caller-owned stages."""
    split = build_verified_reaction_split(store, source_manifest, source_head)
    baseline = run_reaction_baselines(
        split.manifest,
        split.history,
        split.cases,
        expected_manifest_sha256=split.manifest.manifest_sha256,
    )
    model = _run_model(adapter, split)
    freeze = _seal_private_freeze(split, baseline, model)
    targets = materialize_reaction_targets(
        store,
        source_manifest,
        source_head,
        split.manifest,
        split.target_seal,
        freeze,
    )
    result = _score_private(freeze, targets)
    return VerifiedReactionBenchmark(baseline, model, freeze, targets, result)


def _run_model(adapter: LocalReactionModelAdapter, split: ReactionSplit) -> PersonaReactionModelRun:
    if adapter.artifact_path is None:
        raise DataValidationError(
            "reaction_model_verified_source_invalid",
            "Private model run requires a pinned local artifact file.",
        )
    _verify_artifact(adapter)
    profile = build_reaction_profile(split.history, split.manifest.development_history_sha256)
    predictions: dict[ModelReactionArm, tuple[PersonaReactionArmPrediction, ...]] = {
        arm: tuple(
            _predict_private(
                adapter,
                case,
                split.history if arm == "structured_persona" else (),
                arm,
                profile if arm == "structured_persona" else None,
            )
            for case in split.cases
        )
        for arm in ("generic_local_8b", "structured_persona")
    }
    _verify_artifact(adapter)
    return _seal_model_run(adapter, split, predictions)


def _predict_private(
    adapter: LocalReactionModelAdapter,
    case: PersonaReactionCase,
    history: tuple[PersonaReactionHistory, ...],
    arm: ModelReactionArm,
    profile: ReactionDevelopmentProfile | None,
) -> PersonaReactionArmPrediction:
    selected = select_reaction_history(case, history) if history else ()
    raw = post_json(
        adapter.endpoint,
        build_reaction_request(adapter.model, case, selected, arm, profile),
        timeout_seconds=adapter.timeout_seconds,
        max_response_bytes=_MAX_RESPONSE_BYTES,
        error_prefix="reaction_model",
    )
    candidate = parse_reaction_envelope(raw, adapter.model, {item.evidence_id for item in selected})
    _validate_citations(candidate, arm)
    payload: dict[str, object] = {
        "arm": cast(ReactionArm, arm),
        "case_id": case.case_id,
        "predicted_label": candidate.predicted_label,
        "abstained": candidate.predicted_label == "abstain",
        "evidence_ids": candidate.evidence_ids,
        "ranking_score": candidate.ranking_score,
        "target_seen": False,
        "target_text": None,
        "persona_identity": False,
        "calibration_used": False,
        "semantic_adoption": False,
        "core_eligible": False,
    }
    return seal_model(PersonaReactionArmPrediction, payload, "prediction_sha256")


def _seal_model_run(
    adapter: LocalReactionModelAdapter,
    split: ReactionSplit,
    predictions: dict[ModelReactionArm, tuple[PersonaReactionArmPrediction, ...]],
) -> PersonaReactionModelRun:
    payload: dict[str, object] = {
        "manifest_sha256": split.manifest.manifest_sha256,
        "model": adapter.model,
        "revision": adapter.revision,
        "artifact_sha256": adapter.artifact_sha256,
        "decode_sha256": canonical_sha256(
            {"decode": DECODE_SETTINGS, "profile_protocol": "reaction-development-profile/0.1"}
        ),
        "predictions": predictions,
        "source_synthetic": False,
        "local_attested": True,
        "artifact_file_verified": True,
        "endpoint_authentication": "not_cryptographically_authenticated",
        "targets_revealed": False,
        "calibration_used": False,
        "persona_identity_claimed": False,
    }
    return seal_model(PersonaReactionModelRun, payload, "run_sha256")


def _seal_private_freeze(
    split: ReactionSplit,
    baseline: PersonaReactionBaselineRun,
    model: PersonaReactionModelRun,
) -> PersonaReactionPredictionFreeze:
    predictions: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]] = {
        "generic_local_8b": model.predictions["generic_local_8b"],
        "history_majority": baseline.arms["history_majority"],
        "chronological_recency": baseline.arms["chronological_recency"],
        "lexical_retrieval": baseline.arms["lexical_retrieval"],
        "static_profile": baseline.arms["static_profile"],
        "structured_persona": model.predictions["structured_persona"],
    }
    bindings = {
        arm: (
            f"local_model_run:{model.run_sha256}"
            if arm in {"generic_local_8b", "structured_persona"}
            else f"deterministic_run:{baseline.run_sha256}"
        )
        for arm in REACTION_ARMS
    }
    payload: dict[str, object] = {
        "manifest_sha256": split.manifest.manifest_sha256,
        "target_seal_sha256": split.target_seal.seal_sha256,
        "arms": REACTION_ARMS,
        "predictions": predictions,
        "model_bindings": bindings,
        "case_clusters": {item.case_id: item.lineage_component_receipt for item in split.cases},
        "matched_case_ids": split.manifest.sealed_case_ids[:18],
        "synthetic": False,
        "upstream_run_sha256s": (baseline.run_sha256, model.run_sha256),
        "abstention_loss": 0.5,
        "minimum_coverage": 0.75,
        "minimum_effect": 1 / 24,
        "bootstrap_resamples": 2000,
        "bootstrap_alpha": 0.01,
        "bootstrap_seed": 20260719,
        "targets_revealed": False,
        "calibrated": False,
        "persona_quality_claimed": False,
        "automatic_core_promotion": False,
    }
    return seal_model(PersonaReactionPredictionFreeze, payload, "freeze_sha256")


def _score_private(
    freeze: PersonaReactionPredictionFreeze,
    targets: PersonaReactionTargetSet,
) -> PersonaReactionComparisonResult:
    synthetic_freeze = _synthetic_freeze(freeze)
    synthetic_targets = _synthetic_targets(targets, synthetic_freeze)
    synthetic_result = score_reaction_predictions(synthetic_freeze, synthetic_targets)
    payload = synthetic_result.model_dump(mode="json", exclude={"result_sha256"})
    payload.update(
        prediction_freeze_sha256=freeze.freeze_sha256,
        target_set_sha256=targets.target_set_sha256,
    )
    return seal_model(PersonaReactionComparisonResult, payload, "result_sha256")


def _synthetic_freeze(
    freeze: PersonaReactionPredictionFreeze,
) -> PersonaReactionPredictionFreeze:
    payload = freeze.model_dump(mode="json", exclude={"freeze_sha256"})
    payload.update(synthetic=True, upstream_run_sha256s=())
    return seal_model(PersonaReactionPredictionFreeze, payload, "freeze_sha256")


def _synthetic_targets(
    targets: PersonaReactionTargetSet,
    freeze: PersonaReactionPredictionFreeze,
) -> PersonaReactionTargetSet:
    payload = targets.model_dump(mode="json", exclude={"target_set_sha256"})
    payload.update(synthetic=True, prediction_freeze_sha256=freeze.freeze_sha256)
    return seal_model(PersonaReactionTargetSet, payload, "target_set_sha256")


def _validate_citations(candidate: ReactionModelCandidate, arm: ModelReactionArm) -> None:
    invalid = (arm == "generic_local_8b" and bool(candidate.evidence_ids)) or (
        arm == "structured_persona"
        and candidate.predicted_label != "abstain"
        and not candidate.evidence_ids
    )
    if invalid:
        raise AdapterError(
            "reaction_model_citation_invalid", "Reaction model citations contradict its arm."
        )


def _verify_artifact(adapter: LocalReactionModelAdapter) -> None:
    if adapter.artifact_path is None:
        raise DataValidationError(
            "reaction_model_artifact_mismatch", "Reaction model artifact hash does not match."
        )
    verify_local_model_artifact(
        adapter.artifact_path, adapter.artifact_sha256, prefix="reaction_model"
    )


__all__ = ["VerifiedReactionBenchmark", "run_verified_reaction_benchmark"]
