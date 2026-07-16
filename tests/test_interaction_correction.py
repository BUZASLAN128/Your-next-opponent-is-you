from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from ynoy.correction import build_correction_receipt
from ynoy.errors import DataValidationError
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
    MakeProjectRuleDecision,
    MarkTemporaryClaimDecision,
    NarrowScopeClaimDecision,
    NullableReviewText,
    NullReason,
    ProposeForCoreDecision,
    RejectClaimDecision,
    RejectInferenceDecision,
    ReviewOutcome,
    ScopeRef,
    SourceSpan,
    Speaker,
    SpeechAct,
    SplitClaimDecision,
    TargetLayer,
)
from ynoy.review_replay import replay_interaction_review
from ynoy.util import sha256_text

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
_RESPONSE = (
    "Confirm local; reject cloud; split modular and tested; narrow reviews; "
    "temporary rule; project architecture; reject inference; core persona."
)
_SEGMENTS = (
    "Confirm local",
    "reject cloud",
    "split modular and tested",
    "narrow reviews",
    "temporary rule",
    "project architecture",
    "reject inference",
    "core persona",
)


def _known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _unknown(reason: NullReason = NullReason.NOT_STATED) -> NullableReviewText:
    return NullableReviewText(null_reason=reason, authority_to_fill="evidence_required")


def _source_span(text: str) -> SourceSpan:
    start = _RESPONSE.index(text)
    return SourceSpan(character_start=start, character_end=start + len(text), text=text)


def _source_receipt() -> InteractionReceipt:
    prompt = "Classify synthetic review statements."
    return InteractionReceipt(
        record_id=UUID(int=1),
        created_at=_NOW,
        source_name="synthetic-lifecycle",
        conversation_id="synthetic-conversation",
        turn_id="synthetic-turn",
        event_time=_NOW,
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator="fixture://lifecycle/prompt",
            speaker=Speaker.ASSISTANT,
            text=_known(prompt),
            content_sha256=sha256_text(prompt),
        ),
        response=_RESPONSE,
        response_sha256=sha256_text(_RESPONSE),
        subject_id="self",
        scope=ScopeRef(person_id="self"),
        question_resolved=_known("Review eight synthetic atoms."),
        source_data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _claim(index: int, *, target: TargetLayer, modality: ClaimModality) -> AtomicClaimProposal:
    segment = _SEGMENTS[index - 1]
    inference = _known("A removable synthetic inference.") if index == 7 else _unknown()
    return AtomicClaimProposal(
        record_id=UUID(int=100 + index),
        created_at=_NOW,
        receipt_id=UUID(int=1),
        subject_id="self",
        source_spans=(_source_span(segment),),
        literal_normalization=f"Synthetic proposition {index}",
        inference=inference,
        candidate_consequence=_unknown(NullReason.AWAITING_USER_CONFIRMATION),
        speech_act=SpeechAct.REQUIREMENT,
        modality=modality,
        claim_type=AtomicClaimType.POLICY,
        target_layer=target,
        scope=ScopeRef(person_id="self"),
        confidence=ConfidenceDimensions(
            classification=ConfidenceLevel.MEDIUM,
            applicability=ConfidenceLevel.UNKNOWN,
        ),
    )


def _review() -> object:
    targets = (
        TargetLayer.PROTECTED_CONTROL,
        TargetLayer.RESEARCH_VISION,
        TargetLayer.ARCHITECTURE_CANDIDATE,
        TargetLayer.SCOPED_POLICY,
        TargetLayer.PROJECT_CONSTITUTION,
        TargetLayer.ARCHITECTURE_CANDIDATE,
        TargetLayer.PERSONA_CANDIDATE,
        TargetLayer.PERSONA_CANDIDATE,
    )
    claims = tuple(
        _claim(index, target=target, modality=ClaimModality.MUST)
        for index, target in enumerate(targets, start=1)
    )
    return build_interaction_review(_source_receipt(), claims)


def _split_replacements() -> tuple[AtomicClaimProposal, AtomicClaimProposal]:
    return (
        _claim(
            3, target=TargetLayer.ARCHITECTURE_CANDIDATE, modality=ClaimModality.SHOULD
        ).model_copy(
            update={"record_id": UUID(int=301), "source_spans": (_source_span("modular"),)}
        ),
        _claim(3, target=TargetLayer.EXPERIMENT_BACKLOG, modality=ClaimModality.SHOULD).model_copy(
            update={"record_id": UUID(int=302), "source_spans": (_source_span("tested"),)}
        ),
    )


def _all_decisions() -> tuple[object, ...]:
    return (
        ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self"),
        RejectClaimDecision(claim_id=UUID(int=102), subject_id="self", reason="Not applicable."),
        SplitClaimDecision(
            claim_id=UUID(int=103), subject_id="self", replacements=_split_replacements()
        ),
        NarrowScopeClaimDecision(
            claim_id=UUID(int=104),
            subject_id="self",
            replacement_scope=ScopeRef(person_id="self", project="alpha"),
        ),
        MarkTemporaryClaimDecision(
            claim_id=UUID(int=105), subject_id="self", valid_until=_NOW + timedelta(days=7)
        ),
        MakeProjectRuleDecision(
            claim_id=UUID(int=106),
            subject_id="self",
            target_layer=TargetLayer.SCOPED_POLICY,
        ),
        RejectInferenceDecision(claim_id=UUID(int=107), subject_id="self"),
        ProposeForCoreDecision(claim_id=UUID(int=108), subject_id="self"),
    )


def test_every_review_action_replays_without_persistence_or_promotion() -> None:
    review = _review()
    receipt = build_correction_receipt(
        review, _all_decisions(), record_id=UUID(int=500), created_at=_NOW
    )
    state = replay_interaction_review(review, (receipt,))

    assert state.review_status == "reviewed" and not state.pending_claim_ids
    assert tuple(item.outcome for item in state.claims) == (
        ReviewOutcome.CONFIRMED,
        ReviewOutcome.REJECTED,
        ReviewOutcome.SPLIT,
        ReviewOutcome.REVISED,
        ReviewOutcome.REVISED,
        ReviewOutcome.REVISED,
        ReviewOutcome.REVISED,
        ReviewOutcome.CORE_REVIEW_REQUESTED,
    )
    assert not state.claims[1].active and not state.claims[1].effective_claims
    assert len(state.claims[2].effective_claims) == 2
    assert state.claims[3].effective_claims[0].scope.project == "alpha"
    assert state.claims[4].effective_claims[0].scope.valid_until == _NOW + timedelta(days=7)
    assert state.claims[5].effective_claims[0].target_layer == TargetLayer.SCOPED_POLICY
    assert state.claims[6].effective_claims[0].inference.null_reason == NullReason.NOT_APPLICABLE
    assert state.claims[7].core_review_requested and not state.claims[7].core_eligible
    assert not receipt.database_used and not receipt.provider_used
    assert receipt.persistence_status == "not_persisted" and receipt.authority == "none"
    assert (
        not state.database_used and not state.provider_used and not state.automatic_core_promotion
    )


def test_partial_later_decision_supersedes_history_without_rewriting_source() -> None:
    review = _review()
    first = build_correction_receipt(
        review,
        (ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self"),),
        record_id=UUID(int=501),
        created_at=_NOW,
    )
    second = build_correction_receipt(
        review,
        (RejectClaimDecision(claim_id=UUID(int=101), subject_id="self", reason="Changed."),),
        previous_receipt=first,
        record_id=UUID(int=502),
        created_at=_NOW + timedelta(minutes=1),
    )
    state = replay_interaction_review(review, (first, second))

    claim = state.claims[0]
    assert state.review_status == "partially_reviewed" and len(state.pending_claim_ids) == 7
    assert claim.outcome == ReviewOutcome.REJECTED and claim.original.record_id == UUID(int=101)
    assert claim.history[0].superseded_by_receipt_sha256 == second.receipt_sha256
    assert claim.history[1].superseded_by_receipt_sha256 is None


@pytest.mark.parametrize(
    ("decision", "code"),
    [
        (
            ConfirmClaimDecision(claim_id=UUID(int=999), subject_id="self"),
            "correction_claim_unknown",
        ),
        (
            ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="other"),
            "correction_subject_mismatch",
        ),
        (
            NarrowScopeClaimDecision(
                claim_id=UUID(int=104), subject_id="self", replacement_scope=ScopeRef()
            ),
            "correction_scope_not_narrower",
        ),
        (
            MarkTemporaryClaimDecision(claim_id=UUID(int=105), subject_id="self", valid_until=_NOW),
            "correction_temporary_invalid",
        ),
        (
            ProposeForCoreDecision(claim_id=UUID(int=101), subject_id="self"),
            "correction_core_target_invalid",
        ),
    ],
)
def test_builder_rejects_invalid_action_boundaries(decision: object, code: str) -> None:
    with pytest.raises(DataValidationError) as blocked:
        build_correction_receipt(_review(), (decision,), created_at=_NOW)  # type: ignore[arg-type]
    assert blocked.value.code == code


def test_split_must_remain_inside_original_evidence() -> None:
    replacements = list(_split_replacements())
    replacements[0] = replacements[0].model_copy(
        update={"source_spans": (_source_span("Confirm local"),)}
    )
    decision = SplitClaimDecision(
        claim_id=UUID(int=103), subject_id="self", replacements=tuple(replacements)
    )
    with pytest.raises(DataValidationError) as blocked:
        build_correction_receipt(_review(), (decision,), created_at=_NOW)
    assert blocked.value.code == "correction_split_span_invalid"


def test_rejection_reason_must_be_explicit_and_bounded() -> None:
    with pytest.raises(ValidationError):
        RejectClaimDecision(claim_id=UUID(int=102), subject_id="self", reason="   ")


def test_builder_rejects_duplicate_claim_and_foreign_predecessor() -> None:
    review = _review()
    decision = ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self")
    with pytest.raises(DataValidationError) as duplicate:
        build_correction_receipt(review, (decision, decision), created_at=_NOW)
    assert duplicate.value.code == "correction_claim_duplicate"

    first = build_correction_receipt(review, (decision,), created_at=_NOW)
    other = review.model_copy(update={"unknowns": ("another_review",)})
    with pytest.raises(DataValidationError) as predecessor:
        build_correction_receipt(
            other,
            (decision,),
            previous_receipt=first,
            created_at=_NOW + timedelta(minutes=1),
        )
    assert predecessor.value.code == "correction_predecessor_mismatch"
