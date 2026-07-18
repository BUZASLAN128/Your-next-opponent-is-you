from __future__ import annotations

from uuid import UUID

from ynoy.errors import PolicyViolation
from ynoy.models import DataClass
from ynoy.models.formal_decision import AdmittedDecisionClaim
from ynoy.models.formal_runtime import AdoptionChallenge, VerifiedAdoption
from ynoy.util import canonical_sha256, new_id


class SyntheticIndependentAdoptionVerifier:
    """D0-only verifier used to prove binding and replay behavior, not real identity."""

    def __init__(self, *, channel_id: str, verifier_version: str) -> None:
        self.channel_id = channel_id
        self.verifier_version = verifier_version
        self._challenges: dict[UUID, AdoptionChallenge] = {}
        self._receipts: dict[str, VerifiedAdoption] = {}
        self._used: set[UUID] = set()

    def issue(
        self,
        claim: AdmittedDecisionClaim,
        *,
        review_sha256: str,
        expected_head: int,
        challenge_id: UUID | None = None,
        data_class: DataClass = DataClass.PUBLIC_SYNTHETIC,
    ) -> AdoptionChallenge:
        if data_class != DataClass.PUBLIC_SYNTHETIC:
            raise PolicyViolation(
                "real_adoption_authenticator_unavailable",
                "V1 has no trusted authenticator for private adoption.",
            )
        draft = AdoptionChallenge.model_construct(
            challenge_id=challenge_id or new_id(),
            subject_id=claim.identity.subject_id,
            review_sha256=review_sha256,
            claim_id=claim.identity.claim_id,
            claim_tuple_sha256=claim.identity.claim_tuple_sha256,
            full_key=claim.identity.full_key,
            expected_head=expected_head,
            channel_id=self.channel_id,
            verifier_version=self.verifier_version,
            data_class=DataClass.PUBLIC_SYNTHETIC,
            challenge_sha256="0" * 64,
        )
        challenge = _seal_challenge(draft)
        if challenge.challenge_id in self._challenges:
            raise PolicyViolation("adoption_challenge_reused", "Challenge identifier is not fresh.")
        self._challenges[challenge.challenge_id] = challenge
        return challenge

    def verify(self, challenge: AdoptionChallenge, *, response_sha256: str) -> VerifiedAdoption:
        registered = self._challenges.get(challenge.challenge_id)
        if registered != challenge or challenge.challenge_id in self._used:
            raise PolicyViolation("adoption_challenge_invalid", "Adoption challenge is invalid.")
        self._used.add(challenge.challenge_id)
        receipt = _build_receipt(challenge, response_sha256=response_sha256)
        self._receipts[receipt.receipt_sha256] = receipt
        return receipt

    def validate(self, adoption: VerifiedAdoption) -> bool:
        return self._receipts.get(adoption.receipt_sha256) == adoption


def adoption_matches(
    adoption: VerifiedAdoption,
    claim: AdmittedDecisionClaim,
    *,
    review_sha256: str,
    expected_head: int,
) -> bool:
    return (
        adoption.subject_id == claim.identity.subject_id
        and adoption.review_sha256 == review_sha256
        and adoption.claim_id == claim.identity.claim_id
        and adoption.claim_tuple_sha256 == claim.identity.claim_tuple_sha256
        and adoption.full_key == claim.identity.full_key
        and adoption.expected_head == expected_head
    )


def _seal_challenge(draft: AdoptionChallenge) -> AdoptionChallenge:
    payload = draft.model_dump(mode="python")
    payload["challenge_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"challenge_sha256"})
    )
    return AdoptionChallenge.model_validate(payload)


def _build_receipt(challenge: AdoptionChallenge, *, response_sha256: str) -> VerifiedAdoption:
    draft = VerifiedAdoption.model_construct(
        adoption_id=new_id(),
        challenge_id=challenge.challenge_id,
        challenge_sha256=challenge.challenge_sha256,
        subject_id=challenge.subject_id,
        review_sha256=challenge.review_sha256,
        claim_id=challenge.claim_id,
        claim_tuple_sha256=challenge.claim_tuple_sha256,
        full_key=challenge.full_key,
        expected_head=challenge.expected_head,
        channel_id=challenge.channel_id,
        verifier_version=challenge.verifier_version,
        response_sha256=response_sha256,
        data_class=challenge.data_class,
        receipt_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="python")
    payload["receipt_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"receipt_sha256"})
    )
    return VerifiedAdoption.model_validate(payload)
