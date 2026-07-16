from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.interaction_review import build_interaction_review
from ynoy.models import (
    AtomicClaimProposal,
    AtomicClaimType,
    ClaimHolder,
    ClaimModality,
    ConfidenceDimensions,
    ConfidenceLevel,
    DataClass,
    InteractionPrompt,
    InteractionReceipt,
    NullableReviewText,
    NullReason,
    ReviewAction,
    ScopeRef,
    SourceAuthority,
    SourceSpan,
    Speaker,
    SpeechAct,
    TargetLayer,
)
from ynoy.util import sha256_text

_PROMPT = "How should the synthetic prototype run?"
_RESPONSE = "Run locally; use containers when practical."


def _text(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _unknown(reason: NullReason = NullReason.NOT_STATED) -> NullableReviewText:
    return NullableReviewText(null_reason=reason, authority_to_fill="evidence_required")


def _receipt() -> InteractionReceipt:
    return InteractionReceipt(
        record_id=UUID(int=1),
        source_name="synthetic-thread",
        conversation_id="synthetic-conversation",
        turn_id="synthetic-turn",
        event_time=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator="fixture://prompt",
            speaker=Speaker.ASSISTANT,
            text=_text(_PROMPT),
            content_sha256=sha256_text(_PROMPT),
        ),
        response=_RESPONSE,
        response_sha256=sha256_text(_RESPONSE),
        subject_id="self",
        scope=ScopeRef(person_id="self", project="synthetic-pilot"),
        question_resolved=_text("Select a local execution shape."),
        source_data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _span(source_text: str) -> SourceSpan:
    start = _RESPONSE.index(source_text)
    return SourceSpan(
        character_start=start,
        character_end=start + len(source_text),
        text=source_text,
    )


def _claim(
    receipt: InteractionReceipt,
    index: int,
    source_text: str,
    *,
    literal: str,
    speech_act: SpeechAct,
    modality: ClaimModality,
    claim_type: AtomicClaimType,
    target_layer: TargetLayer,
) -> AtomicClaimProposal:
    return AtomicClaimProposal(
        record_id=UUID(int=100 + index),
        receipt_id=receipt.record_id,
        subject_id=receipt.subject_id,
        source_spans=(_span(source_text),),
        literal_normalization=literal,
        inference=_unknown(),
        candidate_consequence=_unknown(NullReason.AWAITING_USER_CONFIRMATION),
        speech_act=speech_act,
        modality=modality,
        claim_type=claim_type,
        target_layer=target_layer,
        scope=receipt.scope,
        confidence=ConfidenceDimensions(
            classification=ConfidenceLevel.MEDIUM,
            applicability=ConfidenceLevel.UNKNOWN,
        ),
    )


def _local_claim(receipt: InteractionReceipt, index: int = 1) -> AtomicClaimProposal:
    return _claim(
        receipt,
        index,
        "Run locally",
        literal="The prototype must support local operation.",
        speech_act=SpeechAct.REQUIREMENT,
        modality=ClaimModality.MUST,
        claim_type=AtomicClaimType.REQUIREMENT,
        target_layer=TargetLayer.PROJECT_CONSTITUTION,
    )


def _container_claim(receipt: InteractionReceipt, index: int = 2) -> AtomicClaimProposal:
    return _claim(
        receipt,
        index,
        "use containers when practical",
        literal="Containers are preferred when practical.",
        speech_act=SpeechAct.PREFERENCE,
        modality=ClaimModality.CONDITIONAL,
        claim_type=AtomicClaimType.PREFERENCE,
        target_layer=TargetLayer.ARCHITECTURE_CANDIDATE,
    )


def test_one_receipt_projects_distinct_atomic_claims_without_promotion() -> None:
    receipt = _receipt()
    local = _local_claim(receipt)
    container = _container_claim(receipt)

    forward = build_interaction_review(receipt, (local, container))
    reverse = build_interaction_review(receipt, (container, local))

    assert forward == reverse
    assert forward.source == receipt and forward.source.response == _RESPONSE
    assert forward.source.prompt.text.value == _PROMPT
    assert tuple(claim.record_id for claim in forward.claims) == (
        local.record_id,
        container.record_id,
    )
    assert tuple(claim.modality for claim in forward.claims) == (
        ClaimModality.MUST,
        ClaimModality.CONDITIONAL,
    )
    assert tuple(claim.target_layer for claim in forward.claims) == (
        TargetLayer.PROJECT_CONSTITUTION,
        TargetLayer.ARCHITECTURE_CANDIDATE,
    )
    assert all(claim.status == "proposed" for claim in forward.claims)
    assert all(claim.confirmation_required and not claim.core_eligible for claim in forward.claims)
    assert forward.review_status == "awaiting_user_confirmation"
    assert forward.allowed_actions == tuple(ReviewAction)
    assert forward.source_data_class == DataClass.PUBLIC_SYNTHETIC
    assert forward.review_data_class == DataClass.PUBLIC_SYNTHETIC
    assert not forward.database_used and not forward.provider_used
    assert forward.persistence_status == "not_persisted"
    assert forward.authority == "none" and not forward.automatic_core_promotion


def test_review_keeps_literal_inference_and_consequence_separate() -> None:
    receipt = _receipt()
    proposal = _container_claim(receipt).model_copy(
        update={
            "inference": _text("The user may value portable execution."),
            "candidate_consequence": _unknown(NullReason.AWAITING_USER_CONFIRMATION),
            "target_layer": TargetLayer.PERSONA_CANDIDATE,
        }
    )

    review = build_interaction_review(receipt, (_local_claim(receipt), proposal))
    claim = review.claims[1]

    assert review.claims[0].target_layer == TargetLayer.PROJECT_CONSTITUTION
    assert claim.target_layer == TargetLayer.PERSONA_CANDIDATE and not claim.core_eligible
    assert claim.literal_normalization == "Containers are preferred when practical."
    assert claim.inference.value == "The user may value portable execution."
    assert claim.candidate_consequence.value is None
    assert claim.candidate_consequence.null_reason == NullReason.AWAITING_USER_CONFIRMATION
    assert claim.confidence.attribution == ConfidenceLevel.HIGH
    assert claim.confidence.classification == ConfidenceLevel.MEDIUM
    assert claim.confidence.applicability == ConfidenceLevel.UNKNOWN


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("empty", "atomic_claims_required"),
        ("receipt", "atomic_claim_receipt_mismatch"),
        ("subject", "atomic_claim_subject_mismatch"),
        ("span_outside", "atomic_claim_span_invalid"),
        ("span_mismatch", "atomic_claim_span_mismatch"),
        ("duplicate", "atomic_claim_duplicate"),
    ],
)
def test_review_fails_closed_on_untrusted_claim_links(case: str, error_code: str) -> None:
    receipt = _receipt()
    claim = _local_claim(receipt)
    claims: tuple[AtomicClaimProposal, ...]
    if case == "empty":
        claims = ()
    elif case == "receipt":
        claims = (claim.model_copy(update={"receipt_id": UUID(int=999)}),)
    elif case == "subject":
        claims = (
            claim.model_copy(update={"subject_id": "other", "scope": ScopeRef(person_id="other")}),
        )
    elif case == "span_outside":
        span = claim.source_spans[0].model_copy(update={"character_end": len(_RESPONSE) + 1})
        claims = (claim.model_copy(update={"source_spans": (span,)}),)
    elif case == "span_mismatch":
        span = claim.source_spans[0].model_copy(update={"text": "Not the source"})
        claims = (claim.model_copy(update={"source_spans": (span,)}),)
    else:
        claims = (
            claim,
            _container_claim(receipt).model_copy(update={"record_id": claim.record_id}),
        )

    with pytest.raises(DataValidationError) as blocked:
        build_interaction_review(receipt, claims)
    assert blocked.value.code == error_code


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("speaker", Speaker.ASSISTANT),
        ("claim_holder", ClaimHolder.ASSISTANT),
        ("source_authority", SourceAuthority.ASSISTANT_CONTEXT),
        ("authorship", "assistant_normalized"),
        ("adoption_status", "explicitly_adopted"),
        ("contains_quoted_content", True),
        ("event_time_precision", "unknown"),
        ("integrity_status", "sealed"),
    ],
)
def test_receipt_rejects_persona_laundering(field: str, value: object) -> None:
    payload = _receipt().model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError):
        InteractionReceipt.model_validate(payload)


@pytest.mark.parametrize(
    ("synthetic", "data_class"),
    [
        (True, DataClass.RAW_CORPUS),
        (False, DataClass.PUBLIC_SYNTHETIC),
        (False, DataClass.DERIVED_IDENTITY),
    ],
)
def test_receipt_rejects_dishonest_source_classification(
    synthetic: bool, data_class: DataClass
) -> None:
    payload = _receipt().model_dump(mode="python")
    payload.update(synthetic=synthetic, source_data_class=data_class)

    with pytest.raises(ValidationError, match="data class"):
        InteractionReceipt.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"authority_to_fill": "user_only"},
        {
            "value": "Known",
            "null_reason": NullReason.NOT_STATED,
            "authority_to_fill": "user_only",
        },
        {"value": "   ", "authority_to_fill": "user_only"},
    ],
)
def test_nullable_review_text_requires_value_xor_reason(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NullableReviewText.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "confirmed"), ("confirmation_required", False), ("core_eligible", True)],
)
def test_builder_rejects_tampered_promotion_state(field: str, value: object) -> None:
    receipt = _receipt()
    claim = _local_claim(receipt).model_copy(update={field: value})

    with pytest.raises(DataValidationError) as blocked:
        build_interaction_review(receipt, (claim,))
    assert blocked.value.code == "atomic_claim_invalid"
