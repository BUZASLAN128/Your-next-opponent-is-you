# ruff: noqa: RUF001 -- Turkish prompt and tokenization are intentional.

from __future__ import annotations

import json
import re
from itertools import combinations
from typing import Annotated, Any

from pydantic import Field, StringConstraints, ValidationError, model_validator

from ynoy.errors import AdapterError, DataValidationError
from ynoy.full_persona.reaction_profile import (
    ReactionDevelopmentProfile,
    reaction_profile_prompt,
)
from ynoy.models.base import StrictModel
from ynoy.models.persona_reaction_benchmark import (
    REACTION_SIGNALS,
    PersonaReactionCase,
    PersonaReactionHistory,
    ReactionPrediction,
)

type EvidenceId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

_TOKEN = re.compile(r"[\wçğıöşü]+", re.I)
_MAX_CASE_CONTEXT_CHARS = 1_200
_MAX_HISTORY_CONTEXT_CHARS = 400
_MAX_HISTORY_RESPONSE_CHARS = 160
MAX_HISTORY_EXAMPLES = 4
_MAX_USER_PACKET_BYTES = 8 * 1024
DECODE_SETTINGS = {
    "temperature": 0,
    "seed": 0,
    "max_tokens": 384,
    "chat_template_kwargs": {"enable_thinking": False},
}


class ReactionModelCandidate(StrictModel):
    predicted_label: ReactionPrediction
    ranking_score: float = Field(ge=0.0, le=1.0)
    evidence_ids: tuple[EvidenceId, ...] = Field(max_length=MAX_HISTORY_EXAMPLES)

    @model_validator(mode="after")
    def citations_are_canonical(self) -> ReactionModelCandidate:
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("reaction model evidence identifiers repeat or are unsorted")
        return self


def build_reaction_request(
    model: str,
    case: PersonaReactionCase,
    history: tuple[PersonaReactionHistory, ...],
    arm: str,
    profile: ReactionDevelopmentProfile | None = None,
) -> dict[str, object]:
    packet = {
        "arm": arm,
        "context": _bounded_context(case.context, _MAX_CASE_CONTEXT_CHARS),
        "history": [_history_packet(item) for item in history],
        "development_profile": reaction_profile_prompt(profile) if profile else None,
        "allowed_reactions": (*REACTION_SIGNALS, "abstain"),
        "score_semantics": "raw_ranking_not_probability",
        "output_contract": {
            "predicted_label": "one allowed_reactions value",
            "ranking_score": "number from 0 through 1",
            "evidence_ids": "sorted supplied history ids only; empty for generic",
        },
    }
    encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_USER_PACKET_BYTES:
        raise DataValidationError(
            "reaction_model_packet_oversized", "Reaction model packet exceeded its byte cap."
        )
    system = (
        "Önceki bağlama göre kullanıcının bir sonraki tepki türünü tahmin et. Development profile "
        "hedeflerden önceki bütün gelişim geçmişinin küçük özetidir; örnekler olaya en yakın "
        "kanıtlardır. Bunları prior olarak kullan; kimlik, hafıza veya eylem iddiası kurma. "
        "Kanıt yetersizse "
        "abstain seç. ranking_score kalibre olasılık değildir. Gizli akıl yürütme yazmadan "
        "yalnız şemaya uyan JSON döndür."
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": encoded},
        ],
        **DECODE_SETTINGS,
        "grammar": _candidate_grammar(tuple(item.evidence_id for item in history)),
    }


def parse_reaction_response(
    value: object, *, allowed_evidence_ids: set[str]
) -> ReactionModelCandidate:
    try:
        candidate = ReactionModelCandidate.model_validate(value)
    except ValidationError as exc:
        raise AdapterError(
            "reaction_model_schema_invalid", "Reaction model response did not match its schema."
        ) from exc
    if not set(candidate.evidence_ids) <= allowed_evidence_ids:
        raise AdapterError(
            "reaction_model_citation_invalid", "Reaction model cited unavailable evidence."
        )
    return candidate


def parse_reaction_envelope(
    value: object, expected_model: str, allowed_evidence_ids: set[str]
) -> ReactionModelCandidate:
    try:
        if not isinstance(value, dict) or value.get("model") != expected_model:
            raise AdapterError(
                "reaction_model_identity_mismatch",
                "Reaction endpoint returned a different model identity.",
            )
        choices = value["choices"]
        if not isinstance(choices, list) or not choices:
            raise TypeError
        content = choices[0]["message"]["content"]
        parsed = _parse_content(content)
    except AdapterError:
        raise
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise AdapterError(
            "reaction_model_schema_invalid", "Reaction model envelope is invalid."
        ) from exc
    return parse_reaction_response(parsed, allowed_evidence_ids=allowed_evidence_ids)


def select_reaction_history(
    case: PersonaReactionCase, history: tuple[PersonaReactionHistory, ...]
) -> tuple[PersonaReactionHistory, ...]:
    query = _tokens(" ".join(item.content for item in case.context))
    ranked = sorted(
        history,
        key=lambda item: (
            -len(query & _tokens(" ".join(value.content for value in item.context))),
            -item.event_time.timestamp(),
            item.history_id,
        ),
    )
    return tuple(ranked[:MAX_HISTORY_EXAMPLES])


def _history_packet(item: PersonaReactionHistory) -> dict[str, object]:
    return {
        "evidence_id": item.evidence_id,
        "prior_context": _bounded_context(item.context, _MAX_HISTORY_CONTEXT_CHARS),
        "user_reaction_excerpt": item.observed_response_excerpt[:_MAX_HISTORY_RESPONSE_CHARS],
        "observed_signal": item.observed_signal,
    }


def _bounded_context(context: tuple[Any, ...], limit: int) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    remaining = limit
    for item in context:
        content = str(item.content)[:remaining].strip()
        if content:
            result.append({"speaker": str(item.speaker), "content": content})
            remaining -= len(content)
        if remaining <= 0:
            break
    return result


def _tokens(value: str) -> set[str]:
    return {item.casefold() for item in _TOKEN.findall(value) if len(item) > 1}


def _parse_content(content: object) -> object:
    if not isinstance(content, str):
        return content
    match = re.fullmatch(r"\s*(?:<think>\s*</think>\s*)?(\{.*\})\s*", content, re.S)
    if match is None:
        raise AdapterError(
            "reaction_model_schema_invalid",
            "Reaction model content included non-JSON or non-empty reasoning.",
        )
    return json.loads(match.group(1))


def _candidate_grammar(evidence_ids: tuple[str, ...]) -> str:
    label_values = (*REACTION_SIGNALS, "abstain")
    labels = " | ".join(_grammar_literal(json.dumps(value)) for value in label_values)
    lines = [
        "root ::= object",
        'object ::= "{\\"predicted_label\\":" label '
        '",\\"ranking_score\\":" number ",\\"evidence_ids\\":" evidence-array "}"',
        f"label ::= {labels}",
        'number ::= "0" | "1" | "0." digit | "0." digit digit | "0." digit digit digit',
        "digit ::= [0-9]",
    ]
    if not evidence_ids:
        lines.append('evidence-array ::= "[]"')
        return "\n".join(lines)
    ordered = tuple(sorted(evidence_ids))
    arrays = (
        "[]",
        *(
            json.dumps(values, separators=(",", ":"))
            for size in range(1, len(ordered) + 1)
            for values in combinations(ordered, size)
        ),
    )
    lines.append("evidence-array ::= " + " | ".join(_grammar_literal(value) for value in arrays))
    return "\n".join(lines)


def _grammar_literal(value: str) -> str:
    return json.dumps(value)
