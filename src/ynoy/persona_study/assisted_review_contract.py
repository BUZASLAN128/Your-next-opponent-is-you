from __future__ import annotations

from typing import Any, NoReturn, cast

from pydantic import TypeAdapter, ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import (
    AnnotationPresentation,
    CompletedPersonaProposalReview,
    ExactTextSpan,
    PersonaAnnotationJudgment,
    PersonaModelProposal,
    PersonaProposalBundle,
    PersonaProposalReviewDraft,
    PersonaProposalReviewReceipt,
    SealedPersonaProposalReviewDecision,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_attempts import PROPOSALS_PATH, RETRY_PROPOSALS_PATH
from ynoy.persona_study.assisted_review import (
    QUICK_REVIEW_INSTRUCTIONS,
    QUICK_REVIEW_PATH,
    RETRY_QUICK_REVIEW_PATH,
)
from ynoy.persona_study.label_contract import PRESENTATIONS_PATH, validate_judgment_spans
from ynoy.persona_study.storage_paths import require_regular_file
from ynoy.util import canonical_sha256, sha256_bytes, sha256_text

PRIMARY_REVIEW_PATH = "evaluator/model-proposal-review.json"
PRIMARY_RECEIPT_PATH = "evaluator/model-proposal-review-receipt.json"
RETRY_REVIEW_PATH = "evaluator/model-proposal-review.retry-01.json"
RETRY_RECEIPT_PATH = "evaluator/model-proposal-review-receipt.retry-01.json"


def sealed_review_paths(attempt: str) -> tuple[str, str]:
    if attempt == "primary":
        return PRIMARY_REVIEW_PATH, PRIMARY_RECEIPT_PATH
    if attempt == "retry_01":
        return RETRY_REVIEW_PATH, RETRY_RECEIPT_PATH
    raise ValueError(f"unsupported assisted review attempt: {attempt}")


def active_review_draft(index: StudyArtifactIndex) -> tuple[str, str, str]:
    paths = {item.relative_path: item for item in index.entries}
    for attempt, proposal, draft in (
        ("retry_01", RETRY_PROPOSALS_PATH, RETRY_QUICK_REVIEW_PATH),
        ("primary", PROPOSALS_PATH, QUICK_REVIEW_PATH),
    ):
        if draft in paths:
            if paths[draft].mutable_by != "represented_user":
                raise DataValidationError(
                    "persona_proposal_review_already_sealed",
                    "The represented-user proposal review is already sealed.",
                )
            return attempt, proposal, draft
    raise DataValidationError(
        "persona_proposal_review_unavailable", "No review-ready model proposal draft is available."
    )


def sealed_review_attempt(index: StudyArtifactIndex) -> str | None:
    paths = {item.relative_path for item in index.entries}
    if {RETRY_REVIEW_PATH, RETRY_RECEIPT_PATH} <= paths:
        return "retry_01"
    if {PRIMARY_REVIEW_PATH, PRIMARY_RECEIPT_PATH} <= paths:
        return "primary"
    return None


def load_review_draft(
    store: PersonaStudyStore, study_id: str, path: str
) -> tuple[PersonaProposalReviewDraft, str]:
    try:
        draft_path = store.paths.artifact(study_id, path)
        require_regular_file(draft_path)
        raw = draft_path.read_bytes()
        return PersonaProposalReviewDraft.model_validate_json(raw), sha256_bytes(raw)
    except ValidationError as exc:
        raise DataValidationError(
            "persona_proposal_review_invalid", "The private proposal review draft is invalid."
        ) from exc


def load_proposal_bundle(
    store: PersonaStudyStore, index: StudyArtifactIndex, study_id: str, path: str
) -> PersonaProposalBundle:
    try:
        return PersonaProposalBundle.model_validate_json(
            indexed_immutable_bytes(store, index, study_id, path)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_proposal_review_contract_changed", "The immutable proposal bundle is invalid."
        ) from exc


def load_review_presentations(
    store: PersonaStudyStore, index: StudyArtifactIndex, study_id: str
) -> tuple[AnnotationPresentation, ...]:
    try:
        return TypeAdapter(tuple[AnnotationPresentation, ...]).validate_json(
            indexed_immutable_bytes(store, index, study_id, PRESENTATIONS_PATH)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_proposal_review_contract_changed",
            "The immutable review presentations are invalid.",
        ) from exc


def indexed_immutable_bytes(
    store: PersonaStudyStore, index: StudyArtifactIndex, study_id: str, path: str
) -> bytes:
    matches = tuple(item for item in index.entries if item.relative_path == path)
    if len(matches) != 1 or matches[0].mutable_by != "none":
        raise DataValidationError(
            "persona_proposal_review_contract_changed", "A required immutable artifact is missing."
        )
    artifact = store.paths.artifact(study_id, path)
    require_regular_file(artifact)
    content = artifact.read_bytes()
    if sha256_bytes(content) != matches[0].sha256:
        raise DataValidationError(
            "persona_proposal_review_contract_changed", "An immutable review ancestor changed."
        )
    return content


def validate_review_draft_contract(
    draft: PersonaProposalReviewDraft,
    bundle: PersonaProposalBundle,
    cards: tuple[AnnotationPresentation, ...],
) -> None:
    selected = tuple(item for item in bundle.proposals if item.selected_for_review)
    _validate_selected_proposal_sources(selected, cards)
    expected = tuple((item.presentation_id, item.order, item.chosen_judgment) for item in selected)
    actual = tuple(
        (item.presentation_id, item.order, item.proposed_judgment) for item in draft.actions
    )
    if (
        draft.study_id != bundle.receipt.study_id
        or draft.proposal_receipt_sha256 != bundle.receipt.receipt_sha256
        or draft.instructions != QUICK_REVIEW_INSTRUCTIONS
        or actual != expected
    ):
        raise DataValidationError(
            "persona_proposal_review_contract_changed",
            "The mutable proposal review no longer matches its immutable proposal set.",
        )


def _validate_selected_proposal_sources(
    selected: tuple[PersonaModelProposal, ...], cards: tuple[AnnotationPresentation, ...]
) -> None:
    by_id = {item.presentation_id: item for item in cards}
    if len(by_id) != len(cards):
        _raise_proposal_source_changed()
    for proposal in selected:
        card = by_id.get(proposal.presentation_id)
        if (
            card is None
            or card.order != proposal.order
            or proposal.focus_sha256 != sha256_text(card.focus.content)
        ):
            _raise_proposal_source_changed()
        for proposal_pass in (proposal.direct, proposal.skeptical):
            if proposal_pass is not None:
                validate_judgment_spans(proposal_pass.judgment, card.focus.content)
        if proposal.chosen_judgment is not None:
            validate_judgment_spans(proposal.chosen_judgment, card.focus.content)


def _raise_proposal_source_changed() -> NoReturn:
    raise DataValidationError(
        "persona_proposal_review_contract_changed",
        "A selected proposal no longer matches its immutable presentation source.",
    )


def build_completed_review(
    draft: PersonaProposalReviewDraft, focus_by_id: dict[str, str]
) -> CompletedPersonaProposalReview:
    decisions = []
    for item in draft.actions:
        focus = focus_by_id[item.presentation_id]
        final = _final_judgment(item, focus)
        validate_judgment_spans(final, focus)
        decisions.append(
            SealedPersonaProposalReviewDecision(
                presentation_id=item.presentation_id,
                order=item.order,
                action=cast(Any, item.action),
                proposed_judgment=item.proposed_judgment,
                final_judgment=final,
            )
        )
    return CompletedPersonaProposalReview(
        study_id=draft.study_id,
        proposal_receipt_sha256=draft.proposal_receipt_sha256,
        decisions=tuple(decisions),
    )


def _final_judgment(action: Any, focus: str) -> PersonaAnnotationJudgment:
    if action.action == "confirm":
        return cast(PersonaAnnotationJudgment, action.proposed_judgment)
    if action.action == "correct":
        return cast(PersonaAnnotationJudgment, action.corrected_judgment)
    return _not_mine_judgment(focus)


def _not_mine_judgment(focus: str) -> PersonaAnnotationJudgment:
    return PersonaAnnotationJudgment.model_validate(
        {
            "authorship": "other",
            "claim_holder": "unknown",
            "adoption": "unknown",
            "decision": "unknown",
            "target_layer": "unknown",
            "persona_kind": None,
            "scope": {"risk": "unknown"},
            "rationale_spans": [ExactTextSpan(start=0, end=len(focus), text=focus)],
            "evidence_demand_spans": [],
            "should_abstain": True,
            "exclude_from_persona": True,
            "exclusion_reason": "not_mine",
            "confidence": "high",
            "notes": None,
        }
    )


def build_review_receipt(
    review: CompletedPersonaProposalReview,
) -> PersonaProposalReviewReceipt:
    payload = {
        "study_id": review.study_id,
        "proposal_receipt_sha256": review.proposal_receipt_sha256,
        "review_set_sha256": canonical_sha256(review.model_dump(mode="json")),
        "reviewed_count": len(review.decisions),
        "confirm_count": sum(item.action == "confirm" for item in review.decisions),
        "correct_count": sum(item.action == "correct" for item in review.decisions),
        "not_mine_count": sum(item.action == "not_mine" for item in review.decisions),
        "confirmed_proposal_count": sum(item.action == "confirm" for item in review.decisions),
        "proposal_available_count": sum(
            item.proposed_judgment is not None for item in review.decisions
        ),
    }
    draft = cast(Any, PersonaProposalReviewReceipt).model_construct(
        **payload, receipt_sha256="0" * 64
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"receipt_sha256"}))
    return PersonaProposalReviewReceipt.model_validate({**payload, "receipt_sha256": digest})


def load_sealed_review(
    store: PersonaStudyStore, index: StudyArtifactIndex, study_id: str, attempt: str
) -> tuple[CompletedPersonaProposalReview, PersonaProposalReviewReceipt]:
    review_path, receipt_path = sealed_review_paths(attempt)
    try:
        review = CompletedPersonaProposalReview.model_validate_json(
            indexed_immutable_bytes(store, index, study_id, review_path)
        )
        receipt = PersonaProposalReviewReceipt.model_validate_json(
            indexed_immutable_bytes(store, index, study_id, receipt_path)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_proposal_review_invalid", "The sealed proposal review is invalid."
        ) from exc
    if (
        review.study_id != receipt.study_id
        or review.proposal_receipt_sha256 != receipt.proposal_receipt_sha256
        or canonical_sha256(review.model_dump(mode="json")) != receipt.review_set_sha256
    ):
        raise DataValidationError(
            "persona_proposal_review_contract_changed",
            "The sealed proposal review does not match its receipt.",
        )
    return review, receipt
