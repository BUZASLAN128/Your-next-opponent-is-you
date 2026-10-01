from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from ynoy.correction import build_correction_receipt
from ynoy.interaction_review import build_interaction_review
from ynoy.models import (
    AtomicClaimProposal,
    AtomicClaimType,
    ClaimModality,
    ConfidenceDimensions,
    ConfidenceLevel,
    ConfirmClaimDecision,
    DataClass,
    InteractionPrompt,
    InteractionReceipt,
    NullableReviewText,
    NullReason,
    ScopeRef,
    SourceSpan,
    Speaker,
    SpeechAct,
    TargetLayer,
)
from ynoy.models.correction import InteractionCorrectionReceipt
from ynoy.models.interaction import InteractionReview
from ynoy.util import sha256_text

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
SOURCE_TEXT = "I prefer concise answers."
PROJECT = "synthetic-direct-memory"
SOURCE_ID = "synthetic-source"
RECEIPT_ID = UUID(int=8101)
CLAIM_ID = UUID(int=8102)


def known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def make_native_review(
    *,
    source_id: str = SOURCE_ID,
    project: str = PROJECT,
    event_time: datetime = NOW,
    event_time_precision: Literal["exact", "date_only", "unknown"] = "exact",
) -> InteractionReview:
    """Return a wholly synthetic native review with one exact source span."""
    return build_interaction_review(
        _native_receipt(source_id, project, event_time, event_time_precision),
        (_native_claim(),),
    )


def _native_receipt(
    source_id: str,
    project: str,
    event_time: datetime,
    event_time_precision: Literal["exact", "date_only", "unknown"],
) -> InteractionReceipt:
    prompt = "Classify this synthetic preference."
    return InteractionReceipt(
        record_id=RECEIPT_ID,
        created_at=NOW,
        source_name="synthetic-direct-memory",
        conversation_id=project,
        turn_id=source_id,
        event_time=event_time,
        event_time_precision=event_time_precision,
        prompt=InteractionPrompt(
            source_locator=f"fixture://direct-memory/{source_id}/response",
            speaker=Speaker.ASSISTANT,
            text=known(prompt),
            content_sha256=sha256_text(prompt),
        ),
        response=SOURCE_TEXT,
        response_sha256=sha256_text(SOURCE_TEXT),
        subject_id="self",
        scope=ScopeRef(person_id="self"),
        question_resolved=known("Identify the stated preference."),
        source_data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _native_claim() -> AtomicClaimProposal:
    return AtomicClaimProposal(
        record_id=CLAIM_ID,
        created_at=NOW,
        receipt_id=RECEIPT_ID,
        subject_id="self",
        source_spans=(
            SourceSpan(
                character_start=0,
                character_end=len(SOURCE_TEXT),
                text=SOURCE_TEXT,
            ),
        ),
        literal_normalization="The user prefers concise answers.",
        inference=NullableReviewText(
            null_reason=NullReason.NOT_STATED,
            authority_to_fill="evidence_required",
        ),
        candidate_consequence=NullableReviewText(
            null_reason=NullReason.AWAITING_USER_CONFIRMATION,
            authority_to_fill="evidence_required",
        ),
        speech_act=SpeechAct.PREFERENCE,
        modality=ClaimModality.SHOULD,
        claim_type=AtomicClaimType.PREFERENCE,
        target_layer=TargetLayer.PERSONA_CANDIDATE,
        scope=ScopeRef(person_id="self"),
        confidence=ConfidenceDimensions(
            classification=ConfidenceLevel.MEDIUM,
            applicability=ConfidenceLevel.UNKNOWN,
        ),
    )


def make_native_confirmation(
    review: InteractionReview | None = None,
) -> InteractionCorrectionReceipt:
    selected = review or make_native_review()
    return build_correction_receipt(
        selected,
        (ConfirmClaimDecision(claim_id=CLAIM_ID, subject_id="self"),),
        record_id=UUID(int=8103),
        created_at=NOW,
    )
