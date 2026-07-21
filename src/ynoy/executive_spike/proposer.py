from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.local_http import post_json
from ynoy.models.base import StrictModel
from ynoy.policy import is_loopback_url

_MAX_RESPONSE_BYTES = 16 * 1024
_MODEL_PLAN: Literal["apply_config_repair"] = "apply_config_repair"


class PlanProposal(StrictModel):
    """A model may choose a fixed D0 plan or abstain; it cannot provide a patch."""

    decision: Literal["apply_config_repair", "abstain"]

    def is_apply(self) -> bool:
        return self.decision == _MODEL_PLAN


class ExecutivePlanner(Protocol):
    """Supply one decision for the fixed synthetic fixture without action authority."""

    @property
    def planner_kind(self) -> str: ...

    @property
    def model_identity(self) -> str | None: ...

    def propose(self) -> PlanProposal: ...


@dataclass(frozen=True, slots=True)
class DeterministicFixturePlanner:
    """Return the fixture's only safe repair plan without any model call."""

    planner_kind: str = "deterministic_fixture"
    model_identity: str | None = None

    def propose(self) -> PlanProposal:
        return PlanProposal(decision=_MODEL_PLAN)


@dataclass(frozen=True, slots=True)
class LocalExecutiveProposer:
    """Use an attested loopback model to choose only from D0 plan identifiers."""

    endpoint: str
    model: str
    revision: str
    artifact_sha256: str
    local_attested: bool
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "executive_model_not_loopback", "Executive proposals require a loopback endpoint."
            )
        if not self.local_attested:
            raise PolicyViolation(
                "executive_model_attestation_required",
                "Executive proposals require an explicitly attested local model.",
            )
        valid_identity = (
            self.model.strip() and self.revision.strip() and _is_digest(self.artifact_sha256)
        )
        if not valid_identity:
            raise DataValidationError(
                "executive_model_identity_invalid", "Pinned executive model identity is incomplete."
            )

    @property
    def planner_kind(self) -> str:
        return "attested_local_model"

    @property
    def model_identity(self) -> str:
        return f"{self.model}@{self.revision}:{self.artifact_sha256}"

    def propose(self) -> PlanProposal:
        raw = post_json(
            self.endpoint,
            _request(self.model),
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=_MAX_RESPONSE_BYTES,
            error_prefix="executive_model",
        )
        return _parse(raw, self.model)


def _request(model: str) -> dict[str, object]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return JSON only. You are selecting a plan for the fixed public synthetic "
                    "config-repair-v1 fixture. Choose exactly one decision: apply_config_repair "
                    "or abstain. You cannot edit files, run commands, claim completion, "
                    "or reveal reasoning."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"fixture_status": "broken", "allowed_decisions": [_MODEL_PLAN, "abstain"]}
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 32,
        "response_format": {"type": "json_object", "schema": _response_schema()},
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {"decision": {"type": "string", "enum": [_MODEL_PLAN, "abstain"]}},
        "required": ["decision"],
        "additionalProperties": False,
    }


def _parse(value: object, expected_model: str) -> PlanProposal:
    try:
        if not isinstance(value, dict) or value.get("model") != expected_model:
            raise TypeError
        content = value["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        return PlanProposal.model_validate(parsed)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AdapterError(
            "executive_model_schema_invalid",
            "Executive model response failed the strict plan schema.",
        ) from exc


def _is_digest(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)
