from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.local_http import post_json
from ynoy.models.base import StrictModel
from ynoy.models.persona_action_pilot import (
    ActionPilotCase,
    ActionPilotHistory,
    ActionPilotManifest,
    ActionPilotPrediction,
    ActionPrediction,
    PilotArm,
)
from ynoy.policy import is_loopback_url

_MAX_PROMPT_CHARS = 8 * 1024
_MAX_RESPONSE_BYTES = 64 * 1024
_SIGNALS = (
    "decision",
    "correction",
    "evidence_demand",
    "scope_change",
    "abstention",
    "outcome_feedback",
    "abstain",
)


class _ActionResponse(StrictModel):
    predicted_signal: ActionPrediction
    ranking_score: float


@dataclass(frozen=True, slots=True)
class LocalActionPredictor:
    endpoint: str
    model: str
    revision: str
    artifact_sha256: str
    local_attested: bool
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "action_predictor_not_loopback", "Action pilot requires a loopback endpoint."
            )
        if not self.local_attested:
            raise PolicyViolation(
                "action_predictor_attestation_required",
                "Private action prediction requires explicit local attestation.",
            )
        if not self.model.strip() or not self.revision.strip():
            raise DataValidationError(
                "action_predictor_identity_invalid", "Pinned model identity is incomplete."
            )
        if len(self.artifact_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.artifact_sha256
        ):
            raise DataValidationError(
                "action_predictor_identity_invalid", "Pinned model hash is invalid."
            )

    def predict_arm(
        self,
        manifest: ActionPilotManifest,
        history: tuple[ActionPilotHistory, ...],
        cases: tuple[ActionPilotCase, ...],
        *,
        arm: PilotArm,
    ) -> tuple[ActionPilotPrediction, ...]:
        if tuple(item.case_id for item in cases) != manifest.sealed_case_ids:
            raise DataValidationError(
                "action_predictor_case_mismatch", "Predictor cases differ from the manifest."
            )
        if arm == "generic" and history:
            raise DataValidationError(
                "action_predictor_generic_history", "Generic arm cannot receive personal history."
            )
        if (
            arm == "personalized"
            and tuple(item.case_id for item in history) != manifest.history_case_ids
        ):
            raise DataValidationError(
                "action_predictor_history_mismatch", "Personal history differs from the manifest."
            )
        return tuple(self._predict(case, history, arm) for case in cases)

    def _predict(
        self,
        case: ActionPilotCase,
        history: tuple[ActionPilotHistory, ...],
        arm: PilotArm,
    ) -> ActionPilotPrediction:
        payload = _request(self.model, case, history, arm)
        raw = post_json(
            self.endpoint,
            payload,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=_MAX_RESPONSE_BYTES,
            error_prefix="action_predictor",
        )
        result = _parse(raw, self.model)
        return ActionPilotPrediction(
            arm=arm,
            case_id=case.case_id,
            predicted_signal=result.predicted_signal,
            ranking_score=result.ranking_score,
            model=f"{self.model}@{self.revision}:{self.artifact_sha256}",
            target_seen=False,
        )


def _request(
    model: str,
    case: ActionPilotCase,
    history: tuple[ActionPilotHistory, ...],
    arm: PilotArm,
) -> dict[str, object]:
    packet = {
        "arm": arm,
        "prior_authored_examples": _bounded_history(history),
        "response_preceding_context": _bounded_context(case),
        "allowed_signals": _SIGNALS,
    }
    encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > _MAX_PROMPT_CHARS:
        raise AdapterError(
            "action_predictor_input_too_large", "One action-pilot prompt exceeded its cap."
        )
    system = (
        "Predict the represented user's next observable action category. Return JSON only. "
        "Use only the supplied response-preceding context and, when present, prior authored "
        "examples. Never claim identity, memory, adoption, or persona quality. Choose abstain "
        "when evidence is insufficient. Do not reveal reasoning."
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": encoded},
        ],
        "temperature": 0,
        "max_tokens": 64,
        "response_format": {"type": "json_object", "schema": _response_schema()},
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _history_packet(item: ActionPilotHistory, budget: int) -> dict[str, object]:
    focus = item.focus[: min(768, budget)]
    remaining = max(0, budget - len(focus))
    context = []
    for value in reversed(item.context):
        if len(value.content) <= remaining:
            context.append({"speaker": value.speaker, "content": value.content})
            remaining -= len(value.content)
    context.reverse()
    return {
        "context": context,
        "observed_response": focus,
        "observed_signal": item.primary_signal,
    }


def _bounded_history(history: tuple[ActionPilotHistory, ...]) -> list[dict[str, object]]:
    if not history:
        return []
    per_example = 3 * 1024 // len(history)
    return [_history_packet(item, per_example) for item in history]


def _bounded_context(case: ActionPilotCase) -> list[dict[str, str]]:
    budget = 2 * 1024
    selected: list[dict[str, str]] = []
    for item in reversed(case.context):
        if len(item.content) <= budget:
            selected.append({"speaker": item.speaker, "content": item.content})
            budget -= len(item.content)
    selected.reverse()
    return selected


def _response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "predicted_signal": {"type": "string", "enum": list(_SIGNALS)},
            "ranking_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["predicted_signal", "ranking_score"],
        "additionalProperties": False,
    }


def _parse(value: object, expected_model: str) -> _ActionResponse:
    try:
        if not isinstance(value, dict) or value.get("model") != expected_model:
            raise TypeError
        content = value["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        return _ActionResponse.model_validate(parsed)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AdapterError(
            "action_predictor_schema_invalid", "Action predictor response failed validation."
        ) from exc
