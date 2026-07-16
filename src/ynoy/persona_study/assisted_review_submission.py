from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ynoy.errors import DataValidationError
from ynoy.models import (
    CompletedPersonaProposalReview,
    DataClass,
    PersonaProposalReviewDraft,
    PersonaProposalReviewReceipt,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifact_contract import mutable_entry
from ynoy.persona_study.artifact_mutations import (
    replace_and_seal_mutable_locked,
    replace_mutable_draft_locked,
)
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.assisted_review_contract import (
    active_review_draft,
    build_completed_review,
    build_review_receipt,
    load_proposal_bundle,
    load_review_draft,
    load_review_presentations,
    load_sealed_review,
    sealed_review_attempt,
    sealed_review_paths,
    validate_review_draft_contract,
)
from ynoy.persona_study.label_contract import dependencies, derived_class
from ynoy.util import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class ProposalReviewRecordResult:
    attempt: str
    selected_count: int
    decided_count: int
    pending_count: int
    correction_pending_count: int


@dataclass(frozen=True, slots=True)
class ProposalReviewSubmission:
    attempt: str
    review: CompletedPersonaProposalReview
    receipt: PersonaProposalReviewReceipt
    artifact_index: StudyArtifactIndex


def record_proposal_review_decisions(
    store: PersonaStudyStore,
    study_id: str,
    *,
    confirm_orders: tuple[int, ...] = (),
    not_mine_orders: tuple[int, ...] = (),
    correct_orders: tuple[int, ...] = (),
) -> ProposalReviewRecordResult:
    """Atomically record compact user decisions in the mutable private review draft."""
    requested = _requested_actions(confirm_orders, not_mine_orders, correct_orders)
    store.read_index(study_id)
    with store.study_lock(study_id):
        index = store._read_index_unchecked(study_id)
        attempt, proposal_path, draft_path = active_review_draft(index)
        mutable_entry(index, draft_path)
        bundle = load_proposal_bundle(store, index, study_id, proposal_path)
        cards = load_review_presentations(store, index, study_id)
        draft, draft_sha256 = load_review_draft(store, study_id, draft_path)
        validate_review_draft_contract(draft, bundle, cards)
        by_order = {item.order: item for item in draft.actions}
        _validate_requested_actions(requested, by_order)
        updated_actions = tuple(
            item.model_copy(update={"action": requested[item.order]})
            if item.order in requested and item.action is None
            else item
            for item in draft.actions
        )
        updated = PersonaProposalReviewDraft.model_validate(
            {**draft.model_dump(mode="python"), "actions": updated_actions}
        )
        replace_mutable_draft_locked(
            store,
            study_id,
            draft_path,
            canonical_json_bytes(updated.model_dump(mode="json")),
            draft_sha256,
        )
        return _record_result(attempt, updated)


def submit_proposal_review(store: PersonaStudyStore, study_id: str) -> ProposalReviewSubmission:
    """Seal a complete represented-user proposal audit without promoting persona data."""
    index = store.read_index(study_id)
    replay_attempt = sealed_review_attempt(index)
    if replay_attempt is not None:
        review, receipt = load_sealed_review(store, index, study_id, replay_attempt)
        return ProposalReviewSubmission(replay_attempt, review, receipt, index)
    with store.study_lock(study_id):
        index = store._read_index_unchecked(study_id)
        attempt, proposal_path, draft_path = active_review_draft(index)
        bundle = load_proposal_bundle(store, index, study_id, proposal_path)
        cards = load_review_presentations(store, index, study_id)
        focus_by_id = {item.presentation_id: item.focus.content for item in cards}
        draft, draft_sha256 = load_review_draft(store, study_id, draft_path)
        validate_review_draft_contract(draft, bundle, cards)
        if not all(item.resolved for item in draft.actions):
            raise DataValidationError(
                "persona_proposal_review_incomplete",
                "Every selected proposal card requires a complete represented-user decision.",
            )
        review = build_completed_review(draft, focus_by_id)
        receipt = build_review_receipt(review)
        updated = _seal_review(
            store,
            index,
            study_id,
            attempt,
            draft_path,
            draft,
            draft_sha256,
            review,
            receipt,
        )
        return ProposalReviewSubmission(attempt, review, receipt, updated)


def _seal_review(
    store: PersonaStudyStore,
    index: StudyArtifactIndex,
    study_id: str,
    attempt: str,
    draft_path: str,
    draft: PersonaProposalReviewDraft,
    draft_sha256: str,
    review: CompletedPersonaProposalReview,
    receipt: PersonaProposalReviewReceipt,
) -> StudyArtifactIndex:
    completed_draft = draft.model_copy(update={"completed_by": "represented_user"})
    draft_bytes = canonical_json_bytes(completed_draft.model_dump(mode="json"))
    data_class = derived_class(index)
    raw_class = (
        DataClass.PUBLIC_SYNTHETIC
        if data_class == DataClass.PUBLIC_SYNTHETIC
        else DataClass.RAW_CORPUS
    )
    review_path, receipt_path = sealed_review_paths(attempt)
    sources = dependencies(index)
    payloads = (
        ArtifactPayload(
            review_path,
            canonical_json_bytes(review.model_dump(mode="json")),
            raw_class,
            sources,
        ),
        ArtifactPayload(
            receipt_path,
            canonical_json_bytes(receipt.model_dump(mode="json")),
            data_class,
            sources,
        ),
    )
    return replace_and_seal_mutable_locked(
        store, study_id, draft_path, draft_bytes, payloads, draft_sha256
    )


def _requested_actions(
    confirm: tuple[int, ...], not_mine: tuple[int, ...], correct: tuple[int, ...]
) -> dict[int, str]:
    values = (*confirm, *not_mine, *correct)
    if not values:
        raise DataValidationError(
            "persona_proposal_review_decision_required", "At least one review decision is required."
        )
    if len(values) != len(set(values)):
        raise DataValidationError(
            "persona_proposal_review_decision_conflict",
            "One proposal card received duplicate or conflicting decisions.",
        )
    return {
        **dict.fromkeys(confirm, "confirm"),
        **dict.fromkeys(not_mine, "not_mine"),
        **dict.fromkeys(correct, "correct"),
    }


def _validate_requested_actions(requested: dict[int, str], actions: dict[int, Any]) -> None:
    for order, action in requested.items():
        if order not in actions:
            raise DataValidationError(
                "persona_proposal_review_card_unknown",
                "A decision targeted a card outside the selected review set.",
            )
        current = actions[order]
        if action == "confirm" and current.proposed_judgment is None:
            raise DataValidationError(
                "persona_proposal_review_confirm_unavailable",
                "A card without a stable proposal cannot be confirmed.",
            )
        if current.action is not None and current.action != action:
            raise DataValidationError(
                "persona_proposal_review_decision_already_recorded",
                "A recorded review decision cannot be changed by the compact command.",
            )


def _record_result(attempt: str, draft: PersonaProposalReviewDraft) -> ProposalReviewRecordResult:
    corrections = sum(
        item.action == "correct" and item.corrected_judgment is None for item in draft.actions
    )
    resolved = sum(item.resolved for item in draft.actions)
    return ProposalReviewRecordResult(
        attempt, len(draft.actions), resolved, len(draft.actions) - resolved, corrections
    )
