from __future__ import annotations

from pydantic import ValidationError

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.full_persona.reaction_contracts import seal_model
from ynoy.full_persona.reaction_split import (
    validate_reaction_target_seal,
)
from ynoy.models.persona_reaction_benchmark import (
    REACTION_ARMS,
    PersonaReactionArmPrediction,
    PersonaReactionCase,
    PersonaReactionManifest,
    PersonaReactionTargetSeal,
    ReactionArm,
)
from ynoy.models.persona_reaction_results import PersonaReactionPredictionFreeze


def freeze_reaction_predictions(
    manifest: PersonaReactionManifest,
    target_seal: PersonaReactionTargetSeal,
    predictions: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]],
    *,
    cases: tuple[PersonaReactionCase, ...],
    model_bindings: dict[ReactionArm, str],
    expected_manifest_sha256: str | None = None,
    upstream_run_sha256s: tuple[str, ...] = (),
) -> PersonaReactionPredictionFreeze:
    """Freeze a D0 fixture; private freezes require the verified-store entrypoint."""
    safe_manifest, safe_seal, safe_cases = _validated_inputs(manifest, target_seal, cases)
    if not safe_manifest.synthetic:
        raise PolicyViolation(
            "reaction_freeze_verified_entrypoint_required",
            "Private prediction freeze requires the verified-store entrypoint.",
        )
    expected = expected_manifest_sha256 or safe_manifest.manifest_sha256
    return _freeze_synthetic(
        safe_manifest,
        safe_seal,
        safe_cases,
        predictions,
        model_bindings,
        expected,
        upstream_run_sha256s,
    )


def _freeze_synthetic(
    manifest: PersonaReactionManifest,
    seal: PersonaReactionTargetSeal,
    cases: tuple[PersonaReactionCase, ...],
    predictions: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]],
    model_bindings: dict[ReactionArm, str],
    expected_manifest_sha256: str,
    upstream_run_sha256s: tuple[str, ...],
) -> PersonaReactionPredictionFreeze:
    if not manifest.synthetic:
        raise PolicyViolation(
            "reaction_freeze_verified_entrypoint_required",
            "Private prediction freeze requires the verified-store benchmark entrypoint.",
        )
    checked = _validated_predictions(predictions, manifest.sealed_case_ids)
    if (
        expected_manifest_sha256 != manifest.manifest_sha256
        or tuple(model_bindings) != REACTION_ARMS
        or (not manifest.synthetic and len(upstream_run_sha256s) != 2)
    ):
        raise DataValidationError(
            "reaction_freeze_binding_invalid",
            "Reaction prediction freeze is missing a frozen upstream binding.",
        )
    payload: dict[str, object] = {
        "manifest_sha256": manifest.manifest_sha256,
        "target_seal_sha256": seal.seal_sha256,
        "arms": REACTION_ARMS,
        "predictions": checked,
        "model_bindings": model_bindings,
        "case_clusters": {item.case_id: item.lineage_component_receipt for item in cases},
        "matched_case_ids": manifest.sealed_case_ids[:18],
        "synthetic": manifest.synthetic,
        "upstream_run_sha256s": upstream_run_sha256s,
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


def _validated_inputs(
    manifest: PersonaReactionManifest,
    seal: PersonaReactionTargetSeal,
    cases: tuple[PersonaReactionCase, ...],
) -> tuple[
    PersonaReactionManifest,
    PersonaReactionTargetSeal,
    tuple[PersonaReactionCase, ...],
]:
    try:
        safe_manifest = PersonaReactionManifest.model_validate(manifest.model_dump(mode="json"))
        safe_seal = PersonaReactionTargetSeal.model_validate(seal.model_dump(mode="json"))
        safe_cases = tuple(
            PersonaReactionCase.model_validate(item.model_dump(mode="json")) for item in cases
        )
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_freeze_input_invalid", "Reaction freeze input is invalid."
        ) from exc
    validate_reaction_target_seal(safe_manifest, safe_seal)
    if (
        tuple(item.case_id for item in safe_cases) != safe_manifest.sealed_case_ids
        or len({item.lineage_component_receipt for item in safe_cases}) < 8
    ):
        raise DataValidationError(
            "reaction_freeze_case_invalid", "Reaction freeze cases do not match the manifest."
        )
    return safe_manifest, safe_seal, safe_cases


def _validated_predictions(
    predictions: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]],
    expected_cases: tuple[str, ...],
) -> dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]]:
    if tuple(predictions) != REACTION_ARMS:
        raise DataValidationError(
            "reaction_freeze_arm_invalid", "Reaction freeze requires all six canonical arms."
        )
    try:
        checked = {
            arm: tuple(
                PersonaReactionArmPrediction.model_validate(item.model_dump(mode="json"))
                for item in values
            )
            for arm, values in predictions.items()
        }
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_freeze_prediction_invalid", "Reaction prediction is invalid."
        ) from exc
    if any(
        tuple(item.case_id for item in values) != expected_cases
        or any(item.arm != arm or item.target_seen for item in values)
        for arm, values in checked.items()
    ):
        raise DataValidationError(
            "reaction_freeze_prediction_invalid",
            "Reaction predictions do not match the frozen target-free cases.",
        )
    return checked


__all__ = ["freeze_reaction_predictions"]
