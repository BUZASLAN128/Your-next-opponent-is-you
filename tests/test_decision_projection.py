from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ynoy.correction import build_correction_receipt
from ynoy.decision_brief import resolve_decision_brief
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
    MarkTemporaryClaimDecision,
    NarrowScopeClaimDecision,
    NullableReviewText,
    NullReason,
    RejectClaimDecision,
    ScopeRef,
    SourceSpan,
    Speaker,
    SpeechAct,
    TargetLayer,
)
from ynoy.models.interaction import InteractionReview
from ynoy.review_replay import replay_interaction_review, review_deletion_dependencies
from ynoy.scope import scope_is_active
from ynoy.util import sha256_text

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
_SEGMENTS = (
    "control",
    "project",
    "mission",
    "episode",
    "persona",
    "research",
    "wrong scope",
    "temporary",
    "conflict allow",
    "conflict deny",
)
_RESPONSE = "; ".join(_SEGMENTS) + "."
_TARGETS = (
    TargetLayer.PROTECTED_CONTROL,
    TargetLayer.PROJECT_CONSTITUTION,
    TargetLayer.MISSION_STATE,
    TargetLayer.EPISODIC_MEMORY,
    TargetLayer.PERSONA_CANDIDATE,
    TargetLayer.RESEARCH_VISION,
    TargetLayer.SCOPED_POLICY,
    TargetLayer.SCOPED_POLICY,
    TargetLayer.SCOPED_POLICY,
    TargetLayer.SCOPED_POLICY,
)


def _known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _unknown() -> NullableReviewText:
    return NullableReviewText(
        null_reason=NullReason.NOT_STATED, authority_to_fill="evidence_required"
    )


def _span(text: str) -> SourceSpan:
    start = _RESPONSE.index(text)
    return SourceSpan(character_start=start, character_end=start + len(text), text=text)


def _receipt() -> InteractionReceipt:
    prompt = "Resolve synthetic decisions."
    return InteractionReceipt(
        record_id=UUID(int=1),
        created_at=_NOW,
        source_name="synthetic-brief",
        conversation_id="brief-conversation",
        turn_id="brief-turn",
        event_time=_NOW,
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator="fixture://brief/prompt",
            speaker=Speaker.ASSISTANT,
            text=_known(prompt),
            content_sha256=sha256_text(prompt),
        ),
        response=_RESPONSE,
        response_sha256=sha256_text(_RESPONSE),
        subject_id="self",
        scope=ScopeRef(person_id="self", project="alpha"),
        question_resolved=_known("Resolve scoped synthetic decisions."),
        source_data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _claim(index: int) -> AtomicClaimProposal:
    project = "beta" if index == 7 else (None if index == 9 else "alpha")
    literal = "Shared policy" if index in {9, 10} else f"Brief proposition {index}"
    modality = ClaimModality.MUST_NOT if index == 10 else ClaimModality.MUST
    return AtomicClaimProposal(
        record_id=UUID(int=100 + index),
        created_at=_NOW,
        receipt_id=UUID(int=1),
        subject_id="self",
        source_spans=(_span(_SEGMENTS[index - 1]),),
        literal_normalization=literal,
        inference=_unknown(),
        candidate_consequence=_unknown(),
        speech_act=SpeechAct.REQUIREMENT,
        modality=modality,
        claim_type=AtomicClaimType.POLICY,
        target_layer=_TARGETS[index - 1],
        scope=ScopeRef(person_id="self", project=project),
        confidence=ConfidenceDimensions(
            classification=ConfidenceLevel.MEDIUM,
            applicability=ConfidenceLevel.MEDIUM,
        ),
    )


def _review() -> InteractionReview:
    return build_interaction_review(_receipt(), tuple(_claim(index) for index in range(1, 11)))


def test_brief_partitions_layers_and_excludes_rejected_wrong_scope_and_expired() -> None:
    review = _review()
    decisions = (
        ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self"),
        RejectClaimDecision(claim_id=UUID(int=102), subject_id="self", reason="Reject."),
        ConfirmClaimDecision(claim_id=UUID(int=103), subject_id="self"),
        ConfirmClaimDecision(claim_id=UUID(int=104), subject_id="self"),
        ConfirmClaimDecision(claim_id=UUID(int=105), subject_id="self"),
        ConfirmClaimDecision(claim_id=UUID(int=106), subject_id="self"),
        ConfirmClaimDecision(claim_id=UUID(int=107), subject_id="self"),
        MarkTemporaryClaimDecision(
            claim_id=UUID(int=108), subject_id="self", valid_until=_NOW + timedelta(days=1)
        ),
    )
    receipt = build_correction_receipt(review, decisions, created_at=_NOW)
    state = replay_interaction_review(review, (receipt,))
    brief = resolve_decision_brief(
        state,
        ScopeRef(person_id="self", project="alpha"),
        _NOW + timedelta(days=2),
    )

    assert len(brief.protected_controls) == 1
    assert not brief.project_rules
    assert len(brief.active_missions) == len(brief.episodic_context) == 1
    assert len(brief.persona_candidates) == len(brief.research_candidates) == 1
    assert not brief.persona_candidates[0].core_eligible
    assert brief.pending_claim_ids == (UUID(int=109), UUID(int=110))
    assert not brief.abstained and not brief.conflicts
    assert not brief.database_used and not brief.provider_used
    assert brief.action_status == "not_performed" and not brief.automatic_core_promotion
    assert brief.source_conversation_id == "brief-conversation"
    assert brief.used_correction_receipt_ids == (receipt.record_id,)


def test_exact_opposing_modalities_are_visible_and_force_abstention() -> None:
    review = _review()
    receipt = build_correction_receipt(
        review,
        (
            ConfirmClaimDecision(claim_id=UUID(int=109), subject_id="self"),
            ConfirmClaimDecision(claim_id=UUID(int=110), subject_id="self"),
        ),
        created_at=_NOW,
    )
    state = replay_interaction_review(review, (receipt,))
    brief = resolve_decision_brief(state, ScopeRef(person_id="self", project="alpha"), _NOW)

    assert len(brief.project_rules) == 2 and len(brief.conflicts) == 1
    assert brief.conflicts[0].claim_ids == (UUID(int=109), UUID(int=110))
    assert brief.abstained and brief.abstention_reasons == ("unresolved_conflict",)


def test_replay_is_deterministic_and_rejects_missing_or_tampered_chain() -> None:
    review = _review()
    first = build_correction_receipt(
        review,
        (ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self"),),
        record_id=UUID(int=501),
        created_at=_NOW,
    )
    second = build_correction_receipt(
        review,
        (ConfirmClaimDecision(claim_id=UUID(int=102), subject_id="self"),),
        previous_receipt=first,
        record_id=UUID(int=502),
        created_at=_NOW + timedelta(minutes=1),
    )
    forward = replay_interaction_review(review, (first, second))
    repeated = replay_interaction_review(review, (first, second))
    assert forward == repeated and forward.state_sha256 == repeated.state_sha256

    with pytest.raises(DataValidationError) as duplicate:
        replay_interaction_review(review, (first, first))
    assert duplicate.value.code == "correction_chain_duplicate"
    with pytest.raises(DataValidationError) as time_order:
        build_correction_receipt(
            review,
            (ConfirmClaimDecision(claim_id=UUID(int=103), subject_id="self"),),
            previous_receipt=first,
            created_at=_NOW - timedelta(minutes=1),
        )
    assert time_order.value.code == "correction_time_order"

    with pytest.raises(DataValidationError) as missing:
        replay_interaction_review(review, (second,))
    assert missing.value.code == "correction_chain_sequence"
    with pytest.raises(DataValidationError) as reordered:
        replay_interaction_review(review, (second, first))
    assert reordered.value.code == "correction_chain_sequence"
    with pytest.raises(DataValidationError) as tampered:
        replay_interaction_review(review, (first.model_copy(update={"receipt_sha256": "f" * 64}),))
    assert tampered.value.code == "correction_receipt_invalid"


def test_deletion_projection_includes_source_original_revision_and_receipt() -> None:
    review = _review()
    receipt = build_correction_receipt(
        review,
        (
            NarrowScopeClaimDecision(
                claim_id=UUID(int=101),
                subject_id="self",
                replacement_scope=ScopeRef(person_id="self", project="alpha", role="reviewer"),
            ),
        ),
        created_at=_NOW,
    )
    state = replay_interaction_review(review, (receipt,))
    closure = review_deletion_dependencies(review, (receipt,))
    derived_id = state.claims[0].effective_claims[0].record_id

    assert UUID(int=101) in closure.dependent_claim_ids
    assert derived_id in closure.dependent_claim_ids
    assert closure.dependent_correction_receipt_ids == (receipt.record_id,)
    assert closure.total_dependency_count == 13
    assert not closure.deletion_performed and not closure.database_used


def test_replay_rejects_receipt_from_another_review() -> None:
    review = _review()
    other = review.model_copy(update={"unknowns": ("another_review",)})
    receipt = build_correction_receipt(
        other,
        (ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self"),),
        created_at=_NOW,
    )
    with pytest.raises(DataValidationError) as blocked:
        replay_interaction_review(review, (receipt,))
    assert blocked.value.code == "correction_chain_review"


def test_brief_rejects_wrong_subject_naive_time_and_tampered_state() -> None:
    review = _review()
    receipt = build_correction_receipt(
        review,
        (ConfirmClaimDecision(claim_id=UUID(int=101), subject_id="self"),),
        created_at=_NOW,
    )
    state = replay_interaction_review(review, (receipt,))
    empty = resolve_decision_brief(state, ScopeRef(person_id="self", project="gamma"), _NOW)
    assert empty.abstained
    assert empty.abstention_reasons == ("no_applicable_reviewed_decisions",)

    with pytest.raises(DataValidationError) as subject:
        resolve_decision_brief(state, ScopeRef(person_id="other"), _NOW)
    assert subject.value.code == "decision_brief_subject_mismatch"
    with pytest.raises(DataValidationError) as clock:
        resolve_decision_brief(state, ScopeRef(person_id="self"), _NOW.replace(tzinfo=None))
    assert clock.value.code == "decision_brief_time_invalid"
    with pytest.raises(DataValidationError) as scope_clock:
        scope_is_active(ScopeRef(valid_from=_NOW.replace(tzinfo=None)), _NOW)
    assert scope_clock.value.code == "scope_time_invalid"
    with pytest.raises(DataValidationError) as tampered:
        resolve_decision_brief(
            state.model_copy(update={"state_sha256": "f" * 64}),
            ScopeRef(person_id="self", project="alpha"),
            _NOW,
        )
    assert tampered.value.code == "reviewed_state_invalid"
