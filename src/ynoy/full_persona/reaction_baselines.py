# ruff: noqa: RUF001 -- Turkish tokenization is intentional.

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.reaction_profile import (
    ReactionDevelopmentProfile,
    build_reaction_profile,
)
from ynoy.models.persona_reaction_benchmark import (
    DETERMINISTIC_REACTION_ARMS,
    REACTION_ARMS,
    REACTION_SIGNALS,
    PersonaReactionArmPrediction,
    PersonaReactionBaselineRun,
    PersonaReactionCase,
    PersonaReactionHistory,
    PersonaReactionManifest,
    ReactionArm,
    ReactionPrediction,
    ReactionSignal,
)
from ynoy.util import canonical_sha256

_TOKEN = re.compile(r"[\wçğıöşü]+", re.I)
_JSON_OBJECT = TypeAdapter(dict[str, Any])


def run_reaction_baselines(
    manifest: PersonaReactionManifest,
    history: tuple[PersonaReactionHistory, ...],
    cases: tuple[PersonaReactionCase, ...],
    *,
    expected_manifest_sha256: str,
) -> PersonaReactionBaselineRun:
    """Run four deterministic development-only controls on identical target-free cases."""
    manifest, history, cases = _validated_inputs(manifest, history, cases, expected_manifest_sha256)
    majority = _majority(history)
    recent = max(history, key=lambda item: (item.event_time, item.evidence_id))
    profile = build_reaction_profile(history, manifest.development_history_sha256)
    arms: dict[ReactionArm, tuple[PersonaReactionArmPrediction, ...]] = {
        "history_majority": tuple(
            _prediction("history_majority", case, majority, _support(history, majority))
            for case in cases
        ),
        "chronological_recency": tuple(
            _prediction(
                "chronological_recency", case, recent.observed_signal, (recent.evidence_id,)
            )
            for case in cases
        ),
        "lexical_retrieval": tuple(_lexical_prediction(case, history) for case in cases),
        "static_profile": tuple(
            _static_profile_prediction(case, history, profile) for case in cases
        ),
    }
    payload: dict[str, object] = {
        "manifest_sha256": manifest.manifest_sha256,
        "arms": arms,
        "persona_identity_claimed": False,
        "calibration_used": False,
        "semantic_adoption_claimed": False,
        "automatic_core_promotion": False,
        "comparison_complete": False,
        "status": "deterministic_controls_only",
    }
    return _sealed(PersonaReactionBaselineRun, payload, "run_sha256")


def _validated_inputs(
    manifest: PersonaReactionManifest,
    history: tuple[PersonaReactionHistory, ...],
    cases: tuple[PersonaReactionCase, ...],
    expected_manifest_sha256: str,
) -> tuple[
    PersonaReactionManifest,
    tuple[PersonaReactionHistory, ...],
    tuple[PersonaReactionCase, ...],
]:
    try:
        checked_manifest = PersonaReactionManifest.model_validate(manifest.model_dump(mode="json"))
        checked_history = tuple(
            PersonaReactionHistory.model_validate(item.model_dump(mode="json")) for item in history
        )
        checked_cases = tuple(
            PersonaReactionCase.model_validate(item.model_dump(mode="json")) for item in cases
        )
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_baseline_input_invalid", "Reaction baseline input is invalid."
        ) from exc
    invalid = (
        checked_manifest.manifest_sha256 != expected_manifest_sha256
        or tuple(item.history_id for item in checked_history)
        != checked_manifest.development_history_ids
        or canonical_sha256([item.history_sha256 for item in checked_history])
        != checked_manifest.development_history_sha256
        or tuple(item.case_id for item in checked_cases) != checked_manifest.sealed_case_ids
        or canonical_sha256([item.case_sha256 for item in checked_cases])
        != checked_manifest.sealed_case_set_sha256
        or any(item.event_time >= checked_manifest.temporal_cutoff for item in checked_history)
        or any(item.event_time <= checked_manifest.temporal_cutoff for item in checked_cases)
        or _overlap(checked_history, checked_cases)
    )
    if invalid:
        raise DataValidationError(
            "reaction_baseline_binding_invalid",
            "Reaction baseline inputs do not match the frozen target-free manifest.",
        )
    return checked_manifest, checked_history, checked_cases


def _overlap(
    history: tuple[PersonaReactionHistory, ...], cases: tuple[PersonaReactionCase, ...]
) -> bool:
    return any(
        {getattr(item, field) for item in history} & {getattr(item, field) for item in cases}
        for field in (
            "source_key",
            "source_receipt",
            "conversation_key",
            "lineage_component_receipt",
        )
    )


def _majority(history: tuple[PersonaReactionHistory, ...]) -> ReactionSignal:
    counts = Counter(item.observed_signal for item in history)
    order = {signal: index for index, signal in enumerate(REACTION_SIGNALS)}
    return sorted(REACTION_SIGNALS, key=lambda signal: (-counts[signal], order[signal]))[0]


def _support(
    history: tuple[PersonaReactionHistory, ...], signal: ReactionSignal
) -> tuple[str, ...]:
    return tuple(sorted(item.evidence_id for item in history if item.observed_signal == signal))[:8]


def _lexical_prediction(
    case: PersonaReactionCase, history: tuple[PersonaReactionHistory, ...]
) -> PersonaReactionArmPrediction:
    query = _context_tokens(case.context)
    ranked = sorted(
        history,
        key=lambda item: (
            -len(query & _context_tokens(item.context)),
            -item.event_time.timestamp(),
            item.history_id,
        ),
    )
    best = ranked[0]
    overlap = len(query & _context_tokens(best.context))
    if overlap == 0:
        return _prediction("lexical_retrieval", case, "abstain", ())
    return _prediction("lexical_retrieval", case, best.observed_signal, (best.evidence_id,))


def _static_profile_prediction(
    case: PersonaReactionCase,
    history: tuple[PersonaReactionHistory, ...],
    profile: ReactionDevelopmentProfile,
) -> PersonaReactionArmPrediction:
    query = _context_tokens(case.context)
    scores = {
        signal: len(query & set(profile.discriminative_terms[signal]))
        for signal in REACTION_SIGNALS
    }
    highest = max(scores.values(), default=0)
    label = profile.majority_signal
    if highest > 0:
        label = next(signal for signal in REACTION_SIGNALS if scores[signal] == highest)
    return _prediction("static_profile", case, label, _support(history, label))


def _context_tokens(context: tuple[object, ...]) -> set[str]:
    return {
        token.casefold()
        for item in context
        for token in _TOKEN.findall(str(getattr(item, "content", "")))
        if len(token) > 1
    }


def _prediction(
    arm: ReactionArm,
    case: PersonaReactionCase,
    label: ReactionPrediction,
    evidence_ids: tuple[str, ...],
) -> PersonaReactionArmPrediction:
    payload: dict[str, object] = {
        "arm": arm,
        "case_id": case.case_id,
        "predicted_label": label,
        "abstained": label == "abstain",
        "evidence_ids": tuple(sorted(set(evidence_ids))),
        "ranking_score": None,
        "target_seen": False,
        "target_text": None,
        "persona_identity": False,
        "calibration_used": False,
        "semantic_adoption": False,
        "core_eligible": False,
    }
    return _sealed(PersonaReactionArmPrediction, payload, "prediction_sha256")


def _sealed[ModelT: BaseModel](
    model: type[ModelT], payload: dict[str, object], hash_field: str
) -> ModelT:
    normalized = _JSON_OBJECT.dump_python(payload, mode="json")
    return model.model_validate({**normalized, hash_field: canonical_sha256(normalized)})


__all__ = [
    "DETERMINISTIC_REACTION_ARMS",
    "REACTION_ARMS",
    "run_reaction_baselines",
]
