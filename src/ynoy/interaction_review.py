from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_DECLARATIONS
from ynoy.errors import DataValidationError
from ynoy.models import DataClass
from ynoy.models.interaction import (
    AtomicClaimProposal,
    InteractionReceipt,
    InteractionReview,
    ReviewProviderEvidence,
)
from ynoy.models.review_vocab import ReviewAction

_UNKNOWNS = (
    "classification_not_user_confirmed",
    "applicability_not_user_confirmed",
    "temporal_stability_unknown",
    "core_eligibility_not_evaluated",
    "persistence_not_authorized",
)


def build_interaction_review(
    receipt: InteractionReceipt,
    claims: Sequence[AtomicClaimProposal],
    *,
    provider_evidence: ReviewProviderEvidence | None = None,
) -> InteractionReview:
    """Validate and project atomic proposals without persistence or promotion."""
    safe_receipt = _revalidate_receipt(receipt)
    safe_claims = tuple(_revalidate_claim(claim) for claim in claims)
    safe_provider = _revalidate_provider(provider_evidence)
    _validate_claim_set(safe_receipt, safe_claims)
    ordered = tuple(sorted(safe_claims, key=_claim_key))
    review_class = (
        DataClass.PUBLIC_SYNTHETIC if safe_receipt.synthetic else DataClass.DERIVED_IDENTITY
    )
    return InteractionReview(
        source=safe_receipt,
        subject_id=safe_receipt.subject_id,
        source_data_class=safe_receipt.source_data_class,
        review_data_class=review_class,
        claims=ordered,
        claim_count=len(ordered),
        allowed_actions=tuple(ReviewAction),
        unknowns=_UNKNOWNS,
        proposal_method="local_model" if safe_provider else "manual",
        provider_evidence=safe_provider,
        provider_used=safe_provider is not None,
    )


def _revalidate_receipt(receipt: InteractionReceipt) -> InteractionReceipt:
    if not isinstance(receipt, InteractionReceipt):
        raise DataValidationError(
            "interaction_receipt_required", "Atomic review requires an interaction receipt."
        )
    try:
        return InteractionReceipt.model_validate(receipt.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "interaction_receipt_invalid", "Interaction receipt failed validation."
        ) from exc


def _revalidate_claim(claim: AtomicClaimProposal) -> AtomicClaimProposal:
    if not isinstance(claim, AtomicClaimProposal):
        raise DataValidationError(
            "atomic_claim_required", "Atomic review accepts typed claim proposals only."
        )
    try:
        return AtomicClaimProposal.model_validate(claim.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "atomic_claim_invalid", "Atomic claim proposal failed validation."
        ) from exc


def _revalidate_provider(
    provider: ReviewProviderEvidence | None,
) -> ReviewProviderEvidence | None:
    if provider is None:
        return None
    if not isinstance(provider, ReviewProviderEvidence):
        raise DataValidationError(
            "review_provider_required", "Provider evidence must use the typed local contract."
        )
    try:
        return ReviewProviderEvidence.model_validate(provider.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "review_provider_invalid", "Provider evidence failed strict validation."
        ) from exc


def _validate_claim_set(
    receipt: InteractionReceipt, claims: tuple[AtomicClaimProposal, ...]
) -> None:
    if not claims:
        raise DataValidationError(
            "atomic_claims_required", "Atomic review requires at least one claim proposal."
        )
    if len(claims) > DEFAULT_BOOTSTRAP_MAX_DECLARATIONS:
        raise DataValidationError(
            "atomic_claim_limit", "Atomic review contains too many claim proposals."
        )
    if len({claim.record_id for claim in claims}) != len(claims):
        raise DataValidationError(
            "atomic_claim_duplicate", "Atomic claim proposal identifiers must be unique."
        )
    for claim in claims:
        _validate_claim_link(receipt, claim)


def _validate_claim_link(receipt: InteractionReceipt, claim: AtomicClaimProposal) -> None:
    if claim.receipt_id != receipt.record_id:
        raise DataValidationError(
            "atomic_claim_receipt_mismatch", "Atomic claim belongs to another receipt."
        )
    if claim.subject_id != receipt.subject_id or claim.scope.person_id != receipt.subject_id:
        raise DataValidationError(
            "atomic_claim_subject_mismatch", "Atomic claim belongs to another subject."
        )
    for span in claim.source_spans:
        if span.character_end > len(receipt.response):
            raise DataValidationError(
                "atomic_claim_span_invalid", "Atomic claim source span is outside the response."
            )
        exact = receipt.response[span.character_start : span.character_end]
        if exact != span.text:
            raise DataValidationError(
                "atomic_claim_span_mismatch", "Atomic claim source span does not match evidence."
            )


def _claim_key(claim: AtomicClaimProposal) -> tuple[int, int, str]:
    first = min(claim.source_spans, key=lambda span: (span.character_start, span.character_end))
    return first.character_start, first.character_end, str(claim.record_id)
