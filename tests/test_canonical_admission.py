from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError
from support.canonical_claims import canonical_review, confirmed_admission, core_review_receipt

from ynoy.canonical_admission import build_canonical_admission
from ynoy.correction import build_correction_receipt
from ynoy.errors import DataValidationError
from ynoy.models import CandidateKind, CanonicalClaim, ConfirmClaimDecision, PersonaStratum
from ynoy.models.review_vocab import TargetLayer


def test_confirmed_user_claim_builds_deterministic_exact_span_admission() -> None:
    review, correction, first = confirmed_admission()
    second = build_canonical_admission(
        review,
        (correction,),
        effective_claim_id=review.claims[0].record_id,
    )

    assert first == second
    assert first.claim.explicit_user_adoption is True
    assert first.claim.admission_receipt_id == first.receipt.record_id
    assert first.receipt.adoption_receipt_id == correction.record_id
    assert first.receipt.automatic_core_promotion is False
    assert first.source_links[0].source_receipt_id == review.source.record_id
    assert first.source_links[0].character_start == 0
    assert first.source_links[0].character_end == len(review.source.response)


def test_unreceipted_claim_cannot_be_admitted() -> None:
    review = canonical_review()

    with pytest.raises(DataValidationError) as blocked:
        build_canonical_admission(
            review,
            (),
            effective_claim_id=review.claims[0].record_id,
        )

    assert blocked.value.code == "canonical_claim_not_adopted"


def test_propose_for_core_remains_non_admitting() -> None:
    review = canonical_review(target_layer=TargetLayer.PERSONA_CANDIDATE)
    correction = core_review_receipt(review)

    with pytest.raises(DataValidationError) as blocked:
        build_canonical_admission(
            review,
            (correction,),
            effective_claim_id=review.claims[0].record_id,
            persona_kind=CandidateKind.PREFERENCE,
            persona_stratum=PersonaStratum.DECISIONS_AND_POLICY,
        )

    assert blocked.value.code == "canonical_claim_not_adopted"


def test_persona_admission_requires_explicit_stratum_and_kind() -> None:
    review = canonical_review(target_layer=TargetLayer.PERSONA_CANDIDATE)
    claim = review.claims[0]
    correction = build_correction_receipt(
        review, (ConfirmClaimDecision(claim_id=claim.record_id, subject_id="self"),)
    )

    with pytest.raises(DataValidationError) as blocked:
        build_canonical_admission(
            review,
            (correction,),
            effective_claim_id=claim.record_id,
        )

    assert blocked.value.code == "canonical_persona_classification_required"


def test_non_persona_layer_rejects_persona_classification() -> None:
    review, correction, _ = confirmed_admission()

    with pytest.raises(DataValidationError) as blocked:
        build_canonical_admission(
            review,
            (correction,),
            effective_claim_id=review.claims[0].record_id,
            persona_kind=CandidateKind.PREFERENCE,
            persona_stratum=PersonaStratum.DECISIONS_AND_POLICY,
        )

    assert blocked.value.code == "canonical_persona_classification_required"


def test_supersession_identifier_is_bound_into_claim_and_receipt() -> None:
    replaced = UUID(int=999)
    _, _, admission = confirmed_admission(supersedes_claim_id=replaced)

    assert admission.claim.supersedes_claim_id == replaced
    assert admission.receipt.supersedes_claim_id == replaced


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_holder", "assistant"),
        ("claim_holder", "third_party"),
        ("source_authority", "assistant_context"),
        ("explicit_user_adoption", False),
        ("status", "proposed"),
    ],
)
def test_non_user_or_non_adopted_claim_cannot_form_canonical_model(
    field: str, value: object
) -> None:
    claim = confirmed_admission()[2].claim
    payload = claim.model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError):
        CanonicalClaim.model_validate(payload)
