from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from support.formal_decisions import admitted_claim
from ynoy.adoption import SyntheticIndependentAdoptionVerifier
from ynoy.models.formal_decision import AdmittedDecisionClaim
from ynoy.models.formal_runtime import (
    ReviewAppend,
    TrustedReviewAuthorization,
    VerifiedAdoption,
)
from ynoy.review_append import (
    InMemoryReviewAppendStore,
    build_review_append,
    build_review_authorization,
)
from ynoy.util import new_id

REVIEW_SHA256 = "7" * 64
PAYLOAD_SHA256 = "8" * 64
POLICY_VERSION = "formal-policy/1"
STREAM_ID = "review:self:synthetic"


@dataclass(frozen=True, slots=True)
class RuntimeFixture:
    claim: AdmittedDecisionClaim
    verifier: SyntheticIndependentAdoptionVerifier
    adoption: VerifiedAdoption
    authorization: TrustedReviewAuthorization
    store: InMemoryReviewAppendStore

    def event(
        self,
        *,
        event_id: UUID | None = None,
        expected_revision: int = 0,
        stream_id: str = STREAM_ID,
        event_type: str = "claim_adopted",
        payload_sha256: str = PAYLOAD_SHA256,
        causation_id: UUID | None = None,
    ) -> ReviewAppend:
        return build_review_append(
            event_id=event_id or new_id(),
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_type=event_type,
            payload_sha256=payload_sha256,
            causation_id=causation_id or new_id(),
            authorization=self.authorization,
            adoption=self.adoption,
        )


def runtime_fixture(*, expected_head: int = 0) -> RuntimeFixture:
    claim = admitted_claim()
    verifier = SyntheticIndependentAdoptionVerifier(
        channel_id="synthetic-independent-channel",
        verifier_version="synthetic-verifier/1",
    )
    challenge = verifier.issue(
        claim,
        review_sha256=REVIEW_SHA256,
        expected_head=expected_head,
    )
    adoption = verifier.verify(challenge, response_sha256="9" * 64)
    authorization = build_review_authorization(
        actor_id="local-os-user",
        subject_id=claim.identity.subject_id,
        review_sha256=REVIEW_SHA256,
        stream_id=STREAM_ID,
        allowed_event_types=("claim_adopted",),
        policy_version=POLICY_VERSION,
    )
    store = InMemoryReviewAppendStore(
        policy_version=POLICY_VERSION,
        adoption_verifier=verifier,
    )
    return RuntimeFixture(claim, verifier, adoption, authorization, store)
