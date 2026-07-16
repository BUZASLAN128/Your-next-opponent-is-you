from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.interaction_review import build_interaction_review
from ynoy.local_http import post_json
from ynoy.models import (
    AtomicClaimProposal,
    AtomicClaimType,
    AtomicExtractionCandidate,
    AtomicExtractionResponse,
    ClaimModality,
    ConfidenceDimensions,
    ConfidenceLevel,
    InteractionReceipt,
    InteractionReview,
    NullableReviewText,
    NullReason,
    ReviewProviderEvidence,
    SourceSpan,
    SpeechAct,
    TargetLayer,
)
from ynoy.policy import is_loopback_url
from ynoy.util import canonical_sha256, utc_now

MAX_EXTRACTOR_RESPONSE_BYTES = 2 * 1024 * 1024
_EXTRACTOR_NAMESPACE = UUID("af21a1c3-3818-5b20-88b6-3e4add17eaac")
_NUMBERED_ITEM = re.compile(r"(?:(?<=^)|(?<=\s))\d{1,2}(?:\s*[-.)]|\s+)")


@dataclass(frozen=True, slots=True)
class LocalAtomicExtractor:
    """Use one attested loopback model to propose, never confirm, review atoms."""

    endpoint: str
    model: str
    revision: str
    artifact_sha256: str
    local_attested: bool
    timeout_seconds: float = 180.0

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "local_extractor_not_loopback",
                "The local extractor endpoint must use HTTP on a loopback address.",
            )
        try:
            ReviewProviderEvidence(
                model=self.model,
                revision=self.revision,
                artifact_sha256=self.artifact_sha256,
                local_attested=True,
            )
        except ValidationError as exc:
            raise DataValidationError(
                "local_extractor_identity_invalid",
                "The local extractor requires canonical pinned model identity.",
            ) from exc

    def propose(
        self,
        receipt: InteractionReceipt,
        *,
        generated_at: datetime | None = None,
    ) -> InteractionReview:
        safe_receipt = _revalidate_receipt(receipt)
        if not self.local_attested:
            raise PolicyViolation(
                "local_extractor_attestation_required",
                "Proposal review requires an explicitly attested local model endpoint.",
            )
        raw = post_json(
            self.endpoint,
            _request_payload(safe_receipt, self.model),
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=MAX_EXTRACTOR_RESPONSE_BYTES,
            error_prefix="local_extractor",
        )
        extracted = _parse_response(raw)
        created_at = generated_at or utc_now()
        claims = tuple(
            _materialize_candidate(safe_receipt, candidate, index, created_at)
            for index, candidate in enumerate(extracted.claims, start=1)
        )
        provider = ReviewProviderEvidence(
            model=self.model,
            revision=self.revision,
            artifact_sha256=self.artifact_sha256,
            local_attested=True,
        )
        return build_interaction_review(safe_receipt, claims, provider_evidence=provider)


def _revalidate_receipt(receipt: InteractionReceipt) -> InteractionReceipt:
    if not isinstance(receipt, InteractionReceipt):
        raise DataValidationError(
            "interaction_receipt_required", "Extraction requires a typed interaction receipt."
        )
    try:
        return InteractionReceipt.model_validate(receipt.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "interaction_receipt_invalid", "Interaction receipt failed extraction validation."
        ) from exc


def _request_payload(receipt: InteractionReceipt, model: str) -> dict[str, object]:
    source_segments = _source_segments(receipt.response)
    system = (
        "Return one JSON object with a claims array and no other text. Do not reveal reasoning. "
        "Each item must express exactly one atomic interpretation. Its source_text must exactly "
        "equal one item from allowed_source_spans; the same span may support multiple atoms. Use "
        "occurrence=1 unless that exact span repeats in the original source. Never confirm "
        "truth, adoption, scope, authority, or core eligibility. Project rules, architecture, "
        "experiments, mission state, and persona candidates are different target layers. A system "
        "or project instruction is not persona evidence. Null inference or consequence is allowed. "
        "Allowed speech_act: requirement, preference, correction, proposal, question, aspiration, "
        "rejection, decision, observation. Allowed modality: must, must_not, should, prefer, "
        "conditional, possible, exploratory, unknown. Allowed claim_type: value, goal, preference, "
        "requirement, policy, guardrail, hypothesis, aspiration, metacognitive_rule, "
        "design_principle. Allowed target_layer: project_constitution, protected_control, "
        "architecture_candidate, scoped_policy, mission_state, episodic_memory, "
        "experiment_backlog, research_vision, persona_candidate. Confidence values: high, medium, "
        "low, unknown."
    )
    user = {
        "source_text": receipt.response,
        "allowed_source_spans": source_segments,
        "source_scope": receipt.scope.model_dump(mode="json"),
        "required_item_fields": (
            "source_text, occurrence, literal_normalization, inference, candidate_consequence, "
            "speech_act, modality, claim_type, target_layer, classification_confidence, "
            "applicability_confidence"
        ),
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "temperature": 0,
        "max_tokens": 4096,
        "response_format": {
            "type": "json_object",
            "schema": _response_schema(source_segments),
        },
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _response_schema(source_segments: tuple[str, ...]) -> dict[str, object]:
    nullable_text = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    properties: dict[str, object] = {
        "source_text": {"type": "string", "enum": list(source_segments)},
        "occurrence": {"type": "integer", "minimum": 1, "maximum": 64},
        "literal_normalization": {"type": "string", "minLength": 1},
        "inference": nullable_text,
        "candidate_consequence": nullable_text,
        "speech_act": {"type": "string", "enum": [item.value for item in SpeechAct]},
        "modality": {"type": "string", "enum": [item.value for item in ClaimModality]},
        "claim_type": {"type": "string", "enum": [item.value for item in AtomicClaimType]},
        "target_layer": {"type": "string", "enum": [item.value for item in TargetLayer]},
        "classification_confidence": {
            "type": "string",
            "enum": [item.value for item in ConfidenceLevel],
        },
        "applicability_confidence": {
            "type": "string",
            "enum": [item.value for item in ConfidenceLevel],
        },
    }
    return {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    }


def _source_segments(source: str) -> tuple[str, ...]:
    starts = [match.start() for match in _NUMBERED_ITEM.finditer(source)]
    if len(starts) < 2:
        return (source,)
    if starts[0] > 0 and source[: starts[0]].strip():
        starts.insert(0, 0)
    starts = starts[:64]
    segments = tuple(
        source[start : starts[index + 1] if index + 1 < len(starts) else len(source)].strip()
        for index, start in enumerate(starts)
    )
    return tuple(segment for segment in segments if segment)


def _parse_response(value: object) -> AtomicExtractionResponse:
    try:
        if not isinstance(value, dict):
            raise TypeError
        content = value["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        return AtomicExtractionResponse.model_validate(parsed)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AdapterError(
            "local_extractor_schema_invalid",
            "The local extractor response did not match the bounded atomic schema.",
        ) from exc


def _materialize_candidate(
    receipt: InteractionReceipt,
    candidate: AtomicExtractionCandidate,
    index: int,
    created_at: datetime,
) -> AtomicClaimProposal:
    start = _nth_occurrence(receipt.response, candidate.source_text, candidate.occurrence)
    if start is None:
        raise DataValidationError(
            "local_extractor_span_invalid",
            "A model proposal did not resolve to its claimed exact source occurrence.",
        )
    if candidate.source_text not in _source_segments(receipt.response):
        raise DataValidationError(
            "local_extractor_segment_invalid",
            "A model proposal did not use one of the deterministic source segments.",
        )
    digest = canonical_sha256(candidate.model_dump(mode="json"))
    return AtomicClaimProposal(
        record_id=uuid5(_EXTRACTOR_NAMESPACE, f"{receipt.record_id}:{index}:{digest}"),
        created_at=created_at,
        receipt_id=receipt.record_id,
        subject_id=receipt.subject_id,
        source_spans=(
            SourceSpan(
                character_start=start,
                character_end=start + len(candidate.source_text),
                text=candidate.source_text,
            ),
        ),
        literal_normalization=candidate.literal_normalization,
        inference=_review_text(candidate.inference, NullReason.NOT_STATED),
        candidate_consequence=_review_text(
            candidate.candidate_consequence, NullReason.AWAITING_USER_CONFIRMATION
        ),
        speech_act=candidate.speech_act,
        modality=candidate.modality,
        claim_type=candidate.claim_type,
        target_layer=candidate.target_layer,
        scope=receipt.scope,
        confidence=ConfidenceDimensions(
            attribution=ConfidenceLevel.HIGH,
            classification=candidate.classification_confidence,
            applicability=candidate.applicability_confidence,
        ),
    )


def _review_text(value: str | None, null_reason: NullReason) -> NullableReviewText:
    if value is None:
        return NullableReviewText(
            null_reason=null_reason,
            authority_to_fill="evidence_required",
        )
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _nth_occurrence(source: str, exact: str, occurrence: int) -> int | None:
    start = -1
    for _ in range(occurrence):
        start = source.find(exact, start + 1)
        if start < 0:
            return None
    return start
