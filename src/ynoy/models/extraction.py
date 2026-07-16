from __future__ import annotations

from pydantic import Field, model_validator

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
from ynoy.models.base import StrictModel
from ynoy.models.review_vocab import (
    AtomicClaimType,
    ClaimModality,
    ConfidenceLevel,
    SpeechAct,
    TargetLayer,
)

MAX_EXTRACTED_CLAIMS = 64


def _is_bounded(value: str) -> bool:
    return (
        bool(value.strip())
        and value == value.strip()
        and len(value.encode("utf-8")) <= DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES
    )


class AtomicExtractionCandidate(StrictModel):
    """Untrusted model proposal that still requires deterministic source linking."""

    source_text: str = Field(min_length=1)
    occurrence: int = Field(default=1, ge=1, le=64)
    literal_normalization: str = Field(min_length=1)
    inference: str | None = None
    candidate_consequence: str | None = None
    speech_act: SpeechAct
    modality: ClaimModality
    claim_type: AtomicClaimType
    target_layer: TargetLayer
    classification_confidence: ConfidenceLevel
    applicability_confidence: ConfidenceLevel

    @model_validator(mode="after")
    def text_is_canonical_and_bounded(self) -> AtomicExtractionCandidate:
        values = (
            self.source_text,
            self.literal_normalization,
            self.inference,
            self.candidate_consequence,
        )
        if any(value is not None and not _is_bounded(value) for value in values):
            raise ValueError("extraction text must be trimmed and bounded")
        return self


class AtomicExtractionResponse(StrictModel):
    claims: tuple[AtomicExtractionCandidate, ...] = Field(
        min_length=1, max_length=MAX_EXTRACTED_CLAIMS
    )

    @model_validator(mode="after")
    def claims_are_unique(self) -> AtomicExtractionResponse:
        keys = tuple(item.model_dump_json() for item in self.claims)
        if len(keys) != len(set(keys)):
            raise ValueError("extractor returned duplicate atomic proposals")
        return self
