from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ynoy.errors import AdapterError, DataValidationError
from ynoy.local_http import post_json
from ynoy.models import DataClass, DecisionLabel, Mode
from ynoy.policy import is_loopback_url

MAX_REASONER_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_ITEM_BYTES = 256 * 1024
MAX_EVIDENCE_TOTAL_BYTES = 1024 * 1024


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    text: str
    data_class: DataClass
    source_kind: str
    decision_label: DecisionLabel | None = None


class ReasonerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Mode
    task: str
    task_data_class: DataClass = DataClass.PRIVATE_TASK
    evidence: tuple[EvidenceItem, ...]
    allowed_labels: tuple[DecisionLabel, ...] = tuple(DecisionLabel)


class ReasonerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    predicted_label: DecisionLabel = DecisionLabel.UNKNOWN
    confidence: float = Field(ge=0.0, le=1.0)
    unknowns: tuple[str, ...] = ()


class Reasoner(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def is_local(self) -> bool: ...

    def complete(self, request: ReasonerRequest) -> ReasonerResponse: ...


@dataclass(frozen=True, slots=True)
class LocalOpenAIReasoner:
    endpoint: str
    model: str
    timeout_seconds: float = 120.0
    name: str = "local_openai_compatible"
    is_local: bool = False

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "local_reasoner_not_loopback",
                "The local reasoner endpoint must use HTTP on a loopback address.",
            )

    def complete(self, request: ReasonerRequest) -> ReasonerResponse:
        ensure_reasoner_data_boundary(self, request.evidence, request.task_data_class)
        system = (
            "Return one JSON object with answer, predicted_label, confidence, and unknowns. "
            "Use only supplied evidence. Never claim an action, memory write, source read, or "
            "identity fact that is absent. Do not include chain-of-thought. If evidence is "
            "insufficient, predicted_label must be unknown and confidence must be low."
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        result = post_json(
            self.endpoint,
            payload,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=MAX_REASONER_RESPONSE_BYTES,
            error_prefix="local_reasoner",
        )
        try:
            if not isinstance(result, dict):
                raise TypeError
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            return ReasonerResponse.model_validate(parsed)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise AdapterError(
                "local_reasoner_schema_invalid",
                "The loopback reasoner response did not match the required schema.",
            ) from exc


@dataclass(frozen=True, slots=True)
class DeterministicReasoner:
    """A non-LLM baseline for reproducible synthetic tests."""

    name: str = "deterministic"
    is_local: bool = True

    def complete(self, request: ReasonerRequest) -> ReasonerResponse:
        labels = [item.decision_label for item in request.evidence if item.decision_label]
        if not labels:
            labels = [
                label
                for item in request.evidence
                for label in DecisionLabel
                if f"decision:{label.value}" in item.text.casefold()
            ]
        if not labels:
            return ReasonerResponse(
                answer="Insufficient personal evidence for a decision prediction.",
                predicted_label=DecisionLabel.UNKNOWN,
                confidence=0.0,
                unknowns=("represented_user_decision",),
            )
        counts = {label: labels.count(label) for label in set(labels)}
        predicted = sorted(counts, key=lambda label: (-counts[label], label.value))[0]
        confidence = counts[predicted] / len(labels)
        return ReasonerResponse(
            answer=f"Predicted decision: {predicted.value}.",
            predicted_label=predicted,
            confidence=confidence,
        )


@dataclass(frozen=True, slots=True)
class MissingLocalReasoner:
    name: str = "local_not_configured"
    is_local: bool = True

    def complete(self, request: ReasonerRequest) -> ReasonerResponse:
        del request
        raise AdapterError(
            "local_reasoner_not_configured",
            "Set YNOY_LOCAL_REASONER_URL to a loopback OpenAI-compatible endpoint.",
        )


def ensure_reasoner_data_boundary(
    reasoner: Reasoner,
    evidence: Sequence[EvidenceItem],
    task_data_class: DataClass,
) -> None:
    total_bytes = 0
    for item in evidence:
        item_bytes = len(item.text.encode("utf-8"))
        if item_bytes > MAX_EVIDENCE_ITEM_BYTES:
            raise DataValidationError(
                "reasoner_evidence_item_too_large",
                "A reasoner evidence item exceeds the 256 KiB limit.",
            )
        total_bytes += item_bytes
    if total_bytes > MAX_EVIDENCE_TOTAL_BYTES:
        raise DataValidationError(
            "reasoner_evidence_total_too_large",
            "Selected reasoner evidence exceeds the 1 MiB packet limit.",
        )
    if reasoner.is_local:
        return
    blocked = ({item.data_class for item in evidence} | {task_data_class}) - {
        DataClass.PUBLIC_SYNTHETIC
    }
    if blocked:
        raise DataValidationError(
            "external_reasoner_persona_blocked",
            "External reasoners are limited to public or synthetic D0 evidence in V1.",
        )
