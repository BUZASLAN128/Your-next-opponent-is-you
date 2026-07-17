from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from ynoy.canonical_admission import build_canonical_admission
from ynoy.correction import build_correction_receipt
from ynoy.interaction_review import build_interaction_review
from ynoy.models import (
    AtomicClaimProposal,
    AtomicClaimType,
    CandidateKind,
    CanonicalClaimAdmission,
    ClaimModality,
    ConfidenceDimensions,
    ConfidenceLevel,
    ConfirmClaimDecision,
    DataClass,
    DecisionLabel,
    InteractionCorrectionReceipt,
    InteractionPrompt,
    InteractionReceipt,
    InteractionReview,
    NullableReviewText,
    NullReason,
    PersonaStratum,
    ProposeForCoreDecision,
    ScopeRef,
    SourceSpan,
    Speaker,
    SpeechAct,
    TargetLayer,
)
from ynoy.util import sha256_text

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
RESPONSE = "Prefer evidence-backed rollback before accepting this change."


def canonical_review(
    *,
    offset: int = 0,
    subject_id: str = "self",
    target_layer: TargetLayer = TargetLayer.SCOPED_POLICY,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> InteractionReview:
    source = _source_receipt(offset, subject_id, valid_from, valid_until)
    span = SourceSpan(character_start=0, character_end=len(RESPONSE), text=RESPONSE)
    claim = AtomicClaimProposal(
        record_id=UUID(int=20_000 + offset),
        created_at=source.created_at,
        receipt_id=source.record_id,
        subject_id=subject_id,
        source_spans=(span,),
        literal_normalization="Prefer evidence-backed rollback before acceptance.",
        inference=unknown(),
        candidate_consequence=unknown(NullReason.AWAITING_USER_CONFIRMATION),
        speech_act=SpeechAct.PREFERENCE,
        modality=ClaimModality.PREFER,
        claim_type=AtomicClaimType.PREFERENCE,
        target_layer=target_layer,
        scope=source.scope,
        confidence=ConfidenceDimensions(
            classification=ConfidenceLevel.HIGH,
            applicability=ConfidenceLevel.MEDIUM,
        ),
    )
    return build_interaction_review(source, (claim,))


def _source_receipt(
    offset: int,
    subject_id: str,
    valid_from: datetime | None,
    valid_until: datetime | None,
) -> InteractionReceipt:
    receipt_id = UUID(int=10_000 + offset)
    prompt = "What rule applies to this synthetic change?"
    return InteractionReceipt(
        record_id=receipt_id,
        created_at=NOW + timedelta(minutes=offset),
        source_name="synthetic-canonical-source",
        conversation_id=f"synthetic-conversation-{offset}",
        turn_id=f"synthetic-turn-{offset}",
        event_time=NOW + timedelta(minutes=offset),
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator=f"fixture://canonical/{offset}",
            speaker=Speaker.ASSISTANT,
            text=known(prompt),
            content_sha256=sha256_text(prompt),
        ),
        response=RESPONSE,
        response_sha256=sha256_text(RESPONSE),
        subject_id=subject_id,
        scope=ScopeRef(
            person_id=subject_id,
            project="synthetic-canonical",
            valid_from=valid_from,
            valid_until=valid_until,
        ),
        question_resolved=known("Choose the governing synthetic rule."),
        source_data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def confirmed_admission(
    *,
    offset: int = 0,
    subject_id: str = "self",
    supersedes_claim_id: UUID | None = None,
    decision_label: DecisionLabel | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    target_layer: TargetLayer = TargetLayer.SCOPED_POLICY,
    persona_kind: CandidateKind | None = None,
    persona_stratum: PersonaStratum | None = None,
) -> tuple[InteractionReview, InteractionCorrectionReceipt, CanonicalClaimAdmission]:
    review = canonical_review(
        offset=offset,
        subject_id=subject_id,
        valid_from=valid_from,
        valid_until=valid_until,
        target_layer=target_layer,
    )
    claim = review.claims[0]
    correction = build_correction_receipt(
        review,
        (ConfirmClaimDecision(claim_id=claim.record_id, subject_id=subject_id),),
        created_at=review.source.created_at + timedelta(seconds=1),
        record_id=UUID(int=30_000 + offset),
    )
    admission = build_canonical_admission(
        review,
        (correction,),
        effective_claim_id=claim.record_id,
        persona_kind=persona_kind,
        persona_stratum=persona_stratum,
        decision_label=decision_label,
        supersedes_claim_id=supersedes_claim_id,
    )
    return review, correction, admission


def core_review_receipt(
    review: InteractionReview,
) -> InteractionCorrectionReceipt:
    claim = review.claims[0]
    return build_correction_receipt(
        review,
        (ProposeForCoreDecision(claim_id=claim.record_id, subject_id=review.subject_id),),
        created_at=review.source.created_at + timedelta(seconds=1),
    )


def known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def unknown(reason: NullReason = NullReason.NOT_STATED) -> NullableReviewText:
    return NullableReviewText(null_reason=reason, authority_to_fill="evidence_required")
