from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.local_http import post_json
from ynoy.models import (
    AnnotationDecision,
    AnnotationPresentation,
    AnnotationScope,
    AnnotationTargetLayer,
    CandidateKind,
    ExactTextSpan,
    LabelAdoption,
    LabelAuthorship,
    LabelClaimHolder,
    LabelConfidence,
    PersonaAnnotationJudgment,
    ReviewProviderEvidence,
)
from ynoy.models.base import StrictModel
from ynoy.policy import is_loopback_url

ProposalPassName = Literal["direct", "skeptical"]
MAX_PERSONA_PROMPT_CHARS = 8 * 1024
MAX_PERSONA_RESPONSE_BYTES = 256 * 1024


class _PersonaCandidate(StrictModel):
    authorship: LabelAuthorship
    claim_holder: LabelClaimHolder
    adoption: LabelAdoption
    decision: AnnotationDecision
    target_layer: AnnotationTargetLayer
    persona_kind: CandidateKind | None
    confidence: LabelConfidence


@dataclass(frozen=True, slots=True)
class LocalPersonaProposer:
    endpoint: str
    model: str
    revision: str
    artifact_sha256: str
    local_attested: bool
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "persona_proposer_not_loopback",
                "The persona proposer endpoint must use HTTP on a loopback address.",
            )
        if not self.local_attested:
            raise PolicyViolation(
                "persona_proposer_attestation_required",
                "Private persona proposals require an explicitly attested local endpoint.",
            )
        try:
            provider = self.provider_evidence
        except ValidationError as exc:
            raise DataValidationError(
                "persona_proposer_identity_invalid",
                "The persona proposer requires canonical pinned model identity.",
            ) from exc
        del provider

    @property
    def provider_evidence(self) -> ReviewProviderEvidence:
        return ReviewProviderEvidence(
            model=self.model,
            revision=self.revision,
            artifact_sha256=self.artifact_sha256,
            local_attested=True,
        )

    def propose(
        self,
        presentation: AnnotationPresentation,
        *,
        pass_name: ProposalPassName,
    ) -> PersonaAnnotationJudgment:
        payload = _request_payload(presentation, self.model, pass_name)
        raw = post_json(
            self.endpoint,
            payload,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=MAX_PERSONA_RESPONSE_BYTES,
            error_prefix="persona_proposer",
        )
        return _parse_response(raw, presentation.focus.content)


def _request_payload(
    presentation: AnnotationPresentation,
    model: str,
    pass_name: ProposalPassName,
) -> dict[str, object]:
    focus = presentation.focus.content
    if len(focus) > MAX_PERSONA_PROMPT_CHARS:
        raise AdapterError(
            "persona_proposer_input_too_large",
            "One bounded persona proposal card exceeded the local prompt limit.",
        )
    context, omitted = _bounded_context(presentation, MAX_PERSONA_PROMPT_CHARS - len(focus))
    caution = (
        "Classify directly while abstaining on missing evidence."
        if pass_name == "direct"
        else "Independently re-check quotation, ownership, adoption, scope, and temporariness."
    )
    system = (
        "Return one JSON object matching the supplied schema and no other text. Do not reveal "
        "reasoning. This is an untrusted proposal, never a user attestation. Structural user role "
        "alone does not prove authorship or current adoption. You may propose self only for an "
        "ordinary direct utterance with no quotation, paste, or third-party marker; it remains "
        "untrusted until user review. Quoted, pasted, third-party, rejected, "
        "hypothetical, ambiguous, and non-persona text must be excluded from persona. Unknown "
        "identity or adoption requires abstention. Project rules are not persona. " + caution
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "context": context,
                        "context_omitted_count": omitted,
                        "focus": focus,
                        "pass": pass_name,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 256,
        "response_format": {"type": "json_object", "schema": _judgment_schema(focus)},
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _bounded_context(
    presentation: AnnotationPresentation, budget: int
) -> tuple[list[dict[str, str]], int]:
    selected: list[dict[str, str]] = []
    remaining = max(0, budget)
    for item in reversed(presentation.context):
        if len(item.content) <= remaining:
            selected.append({"speaker": item.speaker.value, "content": item.content})
            remaining -= len(item.content)
    selected.reverse()
    return selected, len(presentation.context) - len(selected)


def _judgment_schema(focus: str) -> dict[str, object]:
    del focus
    properties: dict[str, object] = {
        "authorship": _enum(LabelAuthorship),
        "claim_holder": _enum(LabelClaimHolder),
        "adoption": _enum(LabelAdoption),
        "decision": _enum(AnnotationDecision),
        "target_layer": _enum(AnnotationTargetLayer),
        "persona_kind": _nullable(_enum(CandidateKind)),
        "confidence": _enum(LabelConfidence),
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _enum(enum_type: type[StrEnum]) -> dict[str, object]:
    values = [item.value for item in enum_type]
    return {"type": "string", "enum": values}


def _nullable(schema: dict[str, object]) -> dict[str, object]:
    return {"anyOf": [schema, {"type": "null"}]}


def _parse_response(value: object, focus: str) -> PersonaAnnotationJudgment:
    try:
        if not isinstance(value, dict):
            raise TypeError
        content = value["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        candidate = _PersonaCandidate.model_validate(parsed)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AdapterError(
            "persona_proposer_schema_invalid",
            "The local persona proposal did not match the bounded schema.",
        ) from exc
    return _materialize_candidate(candidate, focus)


def _materialize_candidate(candidate: _PersonaCandidate, focus: str) -> PersonaAnnotationJudgment:
    reason = _exclusion_reason(candidate)
    excluded = reason is not None
    kind = None
    if candidate.target_layer == AnnotationTargetLayer.PERSONA:
        kind = candidate.persona_kind
    return PersonaAnnotationJudgment(
        authorship=candidate.authorship,
        claim_holder=candidate.claim_holder,
        adoption=candidate.adoption,
        decision=candidate.decision,
        target_layer=candidate.target_layer,
        persona_kind=kind,
        scope=AnnotationScope(risk="unknown"),
        rationale_spans=(ExactTextSpan(start=0, end=len(focus), text=focus),),
        evidence_demand_spans=(),
        should_abstain=excluded,
        exclude_from_persona=excluded,
        exclusion_reason=reason,
        confidence=candidate.confidence,
        notes=None,
    )


def _exclusion_reason(candidate: _PersonaCandidate) -> str | None:
    unknown = (
        candidate.authorship == LabelAuthorship.UNKNOWN
        or candidate.claim_holder == LabelClaimHolder.UNKNOWN
        or candidate.adoption == LabelAdoption.UNKNOWN
        or candidate.decision == AnnotationDecision.UNKNOWN
        or candidate.target_layer == AnnotationTargetLayer.UNKNOWN
        or candidate.confidence == LabelConfidence.UNKNOWN
    )
    if unknown or candidate.confidence != LabelConfidence.HIGH:
        return "uncertain"
    if (
        candidate.authorship != LabelAuthorship.SELF
        or candidate.claim_holder != LabelClaimHolder.SELF
    ):
        return "not_self"
    if candidate.adoption != LabelAdoption.ENDORSED:
        return "not_endorsed"
    if candidate.target_layer != AnnotationTargetLayer.PERSONA:
        return "non_persona_layer"
    if candidate.persona_kind is None:
        return "uncertain"
    return None
