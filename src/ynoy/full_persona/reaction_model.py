from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.full_persona.local_model_artifact import verify_local_model_artifact
from ynoy.full_persona.reaction_contracts import seal_model
from ynoy.full_persona.reaction_model_protocol import (
    DECODE_SETTINGS,
    ReactionModelCandidate,
    build_reaction_request,
    parse_reaction_envelope,
    parse_reaction_response,
    select_reaction_history,
)
from ynoy.full_persona.reaction_profile import (
    ReactionDevelopmentProfile,
    build_reaction_profile,
)
from ynoy.local_http import post_json
from ynoy.models.persona_reaction_benchmark import (
    PersonaReactionArmPrediction,
    PersonaReactionCase,
    PersonaReactionHistory,
    PersonaReactionManifest,
    ReactionArm,
)
from ynoy.models.persona_reaction_results import PersonaReactionModelRun
from ynoy.policy import is_loopback_url
from ynoy.util import canonical_sha256

type ModelReactionArm = Literal["generic_local_8b", "structured_persona"]
type ValidatedModelInputs = tuple[
    PersonaReactionManifest,
    tuple[PersonaReactionHistory, ...],
    tuple[PersonaReactionCase, ...],
]

_MODEL_ARMS: tuple[ModelReactionArm, ...] = ("generic_local_8b", "structured_persona")
_MAX_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class LocalReactionModelAdapter:
    endpoint: str
    model: str
    revision: str
    artifact_sha256: str
    local_attested: bool
    artifact_path: Path | None = None
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "reaction_model_not_loopback", "Reaction model endpoint must be loopback-only."
            )
        if not self.local_attested:
            raise PolicyViolation(
                "reaction_model_attestation_required",
                "Private reaction prediction requires an attested local model.",
            )
        if (
            not self.model.strip()
            or not self.revision.strip()
            or not re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256)
        ):
            raise DataValidationError(
                "reaction_model_identity_invalid", "Reaction model identity is not fully pinned."
            )
        if self.artifact_path is not None:
            verify_local_model_artifact(
                self.artifact_path, self.artifact_sha256, prefix="reaction_model"
            )

    def predict_arm(
        self,
        manifest: PersonaReactionManifest,
        history: tuple[PersonaReactionHistory, ...],
        cases: tuple[PersonaReactionCase, ...],
        *,
        arm: ModelReactionArm,
        expected_manifest_sha256: str | None = None,
    ) -> tuple[PersonaReactionArmPrediction, ...]:
        checked, safe_history, safe_cases = _validate_inputs(
            manifest, history, cases, arm, expected_manifest_sha256
        )
        if not checked.synthetic:
            raise PolicyViolation(
                "reaction_model_verified_entrypoint_required",
                "Private prediction requires the verified-store benchmark entrypoint.",
            )
        profile = (
            build_reaction_profile(safe_history, checked.development_history_sha256)
            if arm == "structured_persona"
            else None
        )
        return tuple(self._predict_one(case, safe_history, arm, profile) for case in safe_cases)

    def _predict_one(
        self,
        case: PersonaReactionCase,
        history: tuple[PersonaReactionHistory, ...],
        arm: ModelReactionArm,
        profile: ReactionDevelopmentProfile | None,
    ) -> PersonaReactionArmPrediction:
        if not case.synthetic or any(not item.synthetic for item in history):
            raise PolicyViolation(
                "reaction_model_verified_entrypoint_required",
                "Private prediction requires the verified-store benchmark entrypoint.",
            )
        selected = select_reaction_history(case, history) if history else ()
        raw = post_json(
            self.endpoint,
            build_reaction_request(self.model, case, selected, arm, profile),
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=_MAX_RESPONSE_BYTES,
            error_prefix="reaction_model",
        )
        candidate = parse_reaction_envelope(
            raw, self.model, {item.evidence_id for item in selected}
        )
        _validate_arm_citations(candidate, arm)
        return _prediction(case, arm, candidate)


def run_reaction_model_arms(
    adapter: LocalReactionModelAdapter,
    manifest: PersonaReactionManifest,
    history: tuple[PersonaReactionHistory, ...],
    cases: tuple[PersonaReactionCase, ...],
    *,
    expected_manifest_sha256: str,
) -> PersonaReactionModelRun:
    """Run both local-model arms with one frozen decoder and identical case order."""
    if not manifest.synthetic:
        raise PolicyViolation(
            "reaction_model_verified_entrypoint_required",
            "Private prediction requires the verified-store benchmark entrypoint.",
        )
    predictions = {
        arm: adapter.predict_arm(
            manifest,
            history if arm == "structured_persona" else (),
            cases,
            arm=arm,
            expected_manifest_sha256=expected_manifest_sha256,
        )
        for arm in _MODEL_ARMS
    }
    return build_reaction_model_run(adapter, manifest, predictions)


def build_reaction_model_run(
    adapter: LocalReactionModelAdapter,
    manifest: PersonaReactionManifest,
    predictions: dict[ModelReactionArm, tuple[PersonaReactionArmPrediction, ...]],
) -> PersonaReactionModelRun:
    """Bind already-produced model arms to one pinned model and decoder receipt."""
    if not manifest.synthetic:
        raise PolicyViolation(
            "reaction_model_verified_entrypoint_required",
            "Private model receipts require the verified-store benchmark entrypoint.",
        )
    payload: dict[str, object] = {
        "manifest_sha256": manifest.manifest_sha256,
        "model": adapter.model,
        "revision": adapter.revision,
        "artifact_sha256": adapter.artifact_sha256,
        "decode_sha256": canonical_sha256(
            {"decode": DECODE_SETTINGS, "profile_protocol": "reaction-development-profile/0.1"}
        ),
        "predictions": predictions,
        "source_synthetic": manifest.synthetic,
        "local_attested": True,
        "artifact_file_verified": adapter.artifact_path is not None,
        "endpoint_authentication": "not_cryptographically_authenticated",
        "targets_revealed": False,
        "calibration_used": False,
        "persona_identity_claimed": False,
    }
    return seal_model(PersonaReactionModelRun, payload, "run_sha256")


def _validate_inputs(
    manifest: PersonaReactionManifest,
    history: tuple[PersonaReactionHistory, ...],
    cases: tuple[PersonaReactionCase, ...],
    arm: ModelReactionArm,
    expected_manifest_sha256: str | None,
) -> ValidatedModelInputs:
    try:
        checked = PersonaReactionManifest.model_validate(manifest.model_dump(mode="json"))
        safe_history = tuple(
            PersonaReactionHistory.model_validate(item.model_dump(mode="json")) for item in history
        )
        safe_cases = tuple(
            PersonaReactionCase.model_validate(item.model_dump(mode="json")) for item in cases
        )
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_model_input_invalid", "Reaction model input is invalid."
        ) from exc
    expected = expected_manifest_sha256 or (checked.manifest_sha256 if checked.synthetic else None)
    case_ids = tuple(item.case_id for item in safe_cases)
    history_bound = (
        not safe_history
        if arm == "generic_local_8b"
        else (
            tuple(item.history_id for item in safe_history) == checked.development_history_ids
            and canonical_sha256([item.history_sha256 for item in safe_history])
            == checked.development_history_sha256
        )
    )
    cases_bound = (
        case_ids == checked.sealed_case_ids
        and canonical_sha256([item.case_sha256 for item in safe_cases])
        == checked.sealed_case_set_sha256
    )
    invalid = (
        expected != checked.manifest_sha256
        or not history_bound
        or not cases_bound
        or any(item.event_time >= checked.temporal_cutoff for item in safe_history)
        or any(item.event_time <= checked.temporal_cutoff for item in safe_cases)
    )
    if invalid:
        raise DataValidationError(
            "reaction_model_binding_invalid", "Reaction model input is outside the frozen split."
        )
    return checked, safe_history, safe_cases


def _validate_arm_citations(candidate: ReactionModelCandidate, arm: ModelReactionArm) -> None:
    invalid = (arm == "generic_local_8b" and bool(candidate.evidence_ids)) or (
        arm == "structured_persona"
        and candidate.predicted_label != "abstain"
        and not candidate.evidence_ids
    )
    if invalid:
        raise AdapterError(
            "reaction_model_citation_invalid", "Reaction model citations contradict its arm."
        )


def _prediction(
    case: PersonaReactionCase,
    arm: ModelReactionArm,
    candidate: ReactionModelCandidate,
) -> PersonaReactionArmPrediction:
    label = candidate.predicted_label
    payload: dict[str, object] = {
        "arm": cast(ReactionArm, arm),
        "case_id": case.case_id,
        "predicted_label": label,
        "abstained": label == "abstain",
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


__all__ = [
    "LocalReactionModelAdapter",
    "build_reaction_model_run",
    "build_reaction_request",
    "parse_reaction_response",
    "run_reaction_model_arms",
]
