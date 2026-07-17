from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid5

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import (
    CandidateKind,
    CandidateStatus,
    CanonicalClaim,
    CanonicalClaimAdmission,
    ClaimAdmissionReceipt,
    ClaimSourceLink,
    DataClass,
    DecisionLabel,
    InteractionCorrectionReceipt,
    InteractionReview,
    PersonaStratum,
)
from ynoy.models.canonical import canonical_claim_digest
from ynoy.models.interaction import AtomicClaimProposal
from ynoy.models.review_state import ReviewedClaimState, ReviewedInteractionState
from ynoy.models.review_vocab import ReviewAction, ReviewOutcome, TargetLayer
from ynoy.review_replay import replay_interaction_review
from ynoy.util import canonical_sha256, sha256_text

_ADMISSION_NAMESPACE = UUID("73473ffb-05d8-589f-a5aa-183bfb605d67")
_SOURCE_LINK_NAMESPACE = UUID("5367de2b-dc9e-570c-84dd-99e8097d4900")


def build_canonical_admission(
    review: InteractionReview,
    correction_receipts: Sequence[InteractionCorrectionReceipt],
    *,
    effective_claim_id: UUID,
    persona_kind: CandidateKind | None = None,
    persona_stratum: PersonaStratum | None = None,
    decision_label: DecisionLabel | None = None,
    supersedes_claim_id: UUID | None = None,
) -> CanonicalClaimAdmission:
    """Build one deterministic admission from explicit reviewed-user evidence."""
    state = replay_interaction_review(review, correction_receipts)
    reviewed, effective = _find_effective_claim(state, effective_claim_id)
    event = reviewed.history[-1]
    if event.action in {ReviewAction.REJECT, ReviewAction.PROPOSE_FOR_CORE}:
        raise DataValidationError(
            "canonical_claim_not_adopted",
            "Rejected or core-review-only proposals cannot enter canonical memory.",
        )
    adoption = _find_adoption_receipt(correction_receipts, event.correction_receipt_id)
    _validate_persona_fields(effective.target_layer, persona_kind, persona_stratum)
    links = _build_source_links(review, effective)
    admission_id = uuid5(_ADMISSION_NAMESPACE, f"{adoption.receipt_sha256}:{effective.record_id}")
    claim = _build_claim(
        effective,
        state,
        admission_id,
        links,
        adoption,
        persona_kind,
        persona_stratum,
        decision_label,
        supersedes_claim_id,
    )
    receipt = _build_admission_receipt(
        claim,
        state,
        event.action,
        adoption,
        links,
        supersedes_claim_id,
    )
    try:
        return CanonicalClaimAdmission(claim=claim, receipt=receipt, source_links=links)
    except ValidationError as exc:
        raise DataValidationError(
            "canonical_admission_invalid", "Canonical admission bindings are inconsistent."
        ) from exc


def _find_effective_claim(
    state: ReviewedInteractionState, claim_id: UUID
) -> tuple[ReviewedClaimState, AtomicClaimProposal]:
    for reviewed in state.claims:
        for effective in reviewed.effective_claims:
            if effective.record_id == claim_id:
                if not reviewed.active or reviewed.outcome in {
                    ReviewOutcome.PENDING,
                    ReviewOutcome.REJECTED,
                    ReviewOutcome.CORE_REVIEW_REQUESTED,
                }:
                    break
                return reviewed, effective
    raise DataValidationError(
        "canonical_claim_not_adopted",
        "Canonical admission requires one active explicitly adopted reviewed claim.",
    )


def _find_adoption_receipt(
    receipts: Sequence[InteractionCorrectionReceipt], receipt_id: UUID
) -> InteractionCorrectionReceipt:
    matches = tuple(item for item in receipts if item.record_id == receipt_id)
    if len(matches) != 1:
        raise DataValidationError(
            "canonical_adoption_receipt_missing",
            "The active reviewed claim must retain its exact user adoption receipt.",
        )
    return matches[0]


def _validate_persona_fields(
    layer: TargetLayer,
    persona_kind: CandidateKind | None,
    persona_stratum: PersonaStratum | None,
) -> None:
    is_persona = layer == TargetLayer.PERSONA_CANDIDATE
    if is_persona != (persona_kind is not None and persona_stratum is not None):
        raise DataValidationError(
            "canonical_persona_classification_required",
            "Persona admissions require an explicit kind and stratum; other layers forbid them.",
        )


def _build_source_links(
    review: InteractionReview, claim: AtomicClaimProposal
) -> tuple[ClaimSourceLink, ...]:
    links: list[ClaimSourceLink] = []
    response = review.source.response
    cluster = canonical_sha256(
        {
            "source_receipt_id": str(review.source.record_id),
            "response_sha256": review.source.response_sha256,
        }
    )
    for span in claim.source_spans:
        if response[span.character_start : span.character_end] != span.text:
            raise DataValidationError(
                "canonical_source_span_mismatch",
                "A canonical claim source span no longer matches the exact user response.",
            )
        span_hash = sha256_text(span.text)
        link_id = uuid5(
            _SOURCE_LINK_NAMESPACE,
            f"{claim.record_id}:{review.source.record_id}:{span.character_start}:"
            f"{span.character_end}:{span_hash}",
        )
        draft = ClaimSourceLink.model_construct(
            record_id=link_id,
            created_at=review.source.created_at,
            claim_id=claim.record_id,
            source_receipt_id=review.source.record_id,
            subject_id=review.subject_id,
            source_data_class=review.source_data_class,
            source_response_sha256=review.source.response_sha256,
            character_start=span.character_start,
            character_end=span.character_end,
            span_text_sha256=span_hash,
            origin_cluster_id=cluster,
            link_sha256="0" * 64,
        )
        links.append(_seal_source_link(draft))
    return tuple(links)


def _build_claim(
    proposal: AtomicClaimProposal,
    state: ReviewedInteractionState,
    admission_id: UUID,
    links: tuple[ClaimSourceLink, ...],
    adoption: InteractionCorrectionReceipt,
    persona_kind: CandidateKind | None,
    persona_stratum: PersonaStratum | None,
    decision_label: DecisionLabel | None,
    supersedes_claim_id: UUID | None,
) -> CanonicalClaim:
    draft = CanonicalClaim.model_construct(
        record_id=proposal.record_id,
        created_at=adoption.created_at,
        subject_id=state.subject_id,
        claim_type=proposal.claim_type,
        target_layer=proposal.target_layer,
        literal_statement=proposal.literal_normalization,
        interpretation=proposal.inference.value,
        candidate_consequence=proposal.candidate_consequence.value,
        persona_kind=persona_kind,
        persona_stratum=persona_stratum,
        scope=proposal.scope,
        decision_label=decision_label,
        status=CandidateStatus.CONFIRMED,
        data_class=state.data_class,
        synthetic=state.data_class == DataClass.PUBLIC_SYNTHETIC,
        admission_receipt_id=admission_id,
        source_link_ids=tuple(item.record_id for item in links),
        supersedes_claim_id=supersedes_claim_id,
        claim_sha256="0" * 64,
    )
    return CanonicalClaim.model_validate(
        {**draft.model_dump(mode="python"), "claim_sha256": canonical_claim_digest(draft)}
    )


def _build_admission_receipt(
    claim: CanonicalClaim,
    state: ReviewedInteractionState,
    action: ReviewAction,
    adoption: InteractionCorrectionReceipt,
    links: tuple[ClaimSourceLink, ...],
    supersedes_claim_id: UUID | None,
) -> ClaimAdmissionReceipt:
    draft = ClaimAdmissionReceipt.model_construct(
        record_id=claim.admission_receipt_id,
        created_at=adoption.created_at,
        claim_id=claim.record_id,
        subject_id=claim.subject_id,
        adoption_action=action,
        adoption_receipt_id=adoption.record_id,
        adoption_receipt_sha256=adoption.receipt_sha256,
        review_sha256=state.review_sha256,
        reviewed_state_sha256=state.state_sha256,
        claim_sha256=claim.claim_sha256,
        source_link_ids=tuple(item.record_id for item in links),
        source_count=len(links),
        data_class=claim.data_class,
        supersedes_claim_id=supersedes_claim_id,
        receipt_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"receipt_sha256"})
    return ClaimAdmissionReceipt.model_validate(
        {**draft.model_dump(mode="python"), "receipt_sha256": canonical_sha256(payload)}
    )


def _seal_source_link(draft: ClaimSourceLink) -> ClaimSourceLink:
    payload = draft.model_dump(mode="json", exclude={"link_sha256"})
    return ClaimSourceLink.model_validate(
        {**draft.model_dump(mode="python"), "link_sha256": canonical_sha256(payload)}
    )
