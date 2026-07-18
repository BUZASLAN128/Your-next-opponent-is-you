from __future__ import annotations

from threading import Lock
from uuid import UUID

from pydantic import ValidationError

from ynoy.adoption import SyntheticIndependentAdoptionVerifier
from ynoy.errors import PolicyViolation
from ynoy.models.formal_runtime import (
    ReviewAppend,
    ReviewAppendAck,
    TrustedReviewAuthorization,
    VerifiedAdoption,
)
from ynoy.util import canonical_sha256


class InMemoryReviewAppendStore:
    """Synthetic linearizable store for expected-head and idempotency proofs."""

    def __init__(
        self,
        *,
        policy_version: str,
        adoption_verifier: SyntheticIndependentAdoptionVerifier,
    ) -> None:
        self.policy_version = policy_version
        self._adoption_verifier = adoption_verifier
        self._lock = Lock()
        self._streams: dict[str, list[ReviewAppend]] = {}
        self._events: dict[UUID, tuple[ReviewAppend, ReviewAppendAck]] = {}

    def append(
        self,
        event: ReviewAppend,
        *,
        adoption: VerifiedAdoption,
        authorization: TrustedReviewAuthorization,
    ) -> ReviewAppendAck:
        event, adoption, authorization = _validated_inputs(event, adoption, authorization)
        with self._lock:
            recorded = self._events.get(event.event_id)
            if recorded is not None:
                return self._retry(recorded, event, adoption, authorization)
            self._validate_new(event, adoption, authorization)
            stream = self._streams.setdefault(event.stream_id, [])
            if event.expected_revision != len(stream):
                raise PolicyViolation(
                    "review_append_head_mismatch", "Review stream head does not match."
                )
            ack = ReviewAppendAck(
                event_id=event.event_id,
                stream_id=event.stream_id,
                revision=len(stream) + 1,
                event_sha256=event.event_sha256,
            )
            stream.append(event)
            self._events[event.event_id] = (event, ack)
            return ack

    def head(self, stream_id: str) -> int:
        with self._lock:
            return len(self._streams.get(stream_id, ()))

    def _retry(
        self,
        recorded: tuple[ReviewAppend, ReviewAppendAck],
        event: ReviewAppend,
        adoption: VerifiedAdoption,
        authorization: TrustedReviewAuthorization,
    ) -> ReviewAppendAck:
        original, ack = recorded
        exact = (
            event == original
            and adoption.receipt_sha256 == original.adoption_receipt_sha256
            and authorization.receipt_sha256 == original.authorization_receipt_sha256
            and _authorization_binds(original, authorization, check_policy=False)
            and self._adoption_verifier.validate(adoption)
        )
        if not exact:
            raise PolicyViolation("review_append_denied", "Review append is not authorized.")
        return ack.model_copy(update={"idempotent_replay": True})

    def _validate_new(
        self,
        event: ReviewAppend,
        adoption: VerifiedAdoption,
        authorization: TrustedReviewAuthorization,
    ) -> None:
        valid = (
            event.policy_version == self.policy_version
            and authorization.policy_version == self.policy_version
            and _authorization_binds(event, authorization, check_policy=True)
            and event.event_type in authorization.allowed_event_types
            and event.adoption_receipt_sha256 == adoption.receipt_sha256
            and adoption.subject_id == event.subject_id
            and adoption.review_sha256 == event.review_sha256
            and adoption.expected_head == event.expected_revision
            and self._adoption_verifier.validate(adoption)
        )
        if not valid:
            raise PolicyViolation("review_append_denied", "Review append is not authorized.")


def build_review_authorization(
    *,
    actor_id: str,
    subject_id: str,
    review_sha256: str,
    stream_id: str,
    allowed_event_types: tuple[str, ...],
    policy_version: str,
) -> TrustedReviewAuthorization:
    draft = TrustedReviewAuthorization.model_construct(
        actor_id=actor_id,
        subject_id=subject_id,
        review_sha256=review_sha256,
        stream_id=stream_id,
        allowed_event_types=allowed_event_types,
        policy_version=policy_version,
        authenticated=True,
        receipt_sha256="0" * 64,
    )
    return _seal_authorization(draft)


def build_review_append(
    *,
    event_id: UUID,
    stream_id: str,
    expected_revision: int,
    event_type: str,
    payload_sha256: str,
    causation_id: UUID,
    authorization: TrustedReviewAuthorization,
    adoption: VerifiedAdoption,
) -> ReviewAppend:
    draft = ReviewAppend.model_construct(
        event_id=event_id,
        stream_id=stream_id,
        expected_revision=expected_revision,
        event_type=event_type,
        payload_sha256=payload_sha256,
        causation_id=causation_id,
        actor_id=authorization.actor_id,
        subject_id=authorization.subject_id,
        review_sha256=authorization.review_sha256,
        adoption_receipt_sha256=adoption.receipt_sha256,
        policy_version=authorization.policy_version,
        authorization_receipt_sha256=authorization.receipt_sha256,
        event_sha256="0" * 64,
    )
    return _seal_event(draft)


def _authorization_binds(
    event: ReviewAppend,
    authorization: TrustedReviewAuthorization,
    *,
    check_policy: bool,
) -> bool:
    common = (
        event.actor_id == authorization.actor_id
        and event.subject_id == authorization.subject_id
        and event.review_sha256 == authorization.review_sha256
        and event.stream_id == authorization.stream_id
        and event.authorization_receipt_sha256 == authorization.receipt_sha256
    )
    return common and (not check_policy or event.policy_version == authorization.policy_version)


def _validated_inputs(
    event: ReviewAppend,
    adoption: VerifiedAdoption,
    authorization: TrustedReviewAuthorization,
) -> tuple[ReviewAppend, VerifiedAdoption, TrustedReviewAuthorization]:
    try:
        return (
            ReviewAppend.model_validate(event.model_dump(mode="python")),
            VerifiedAdoption.model_validate(adoption.model_dump(mode="python")),
            TrustedReviewAuthorization.model_validate(authorization.model_dump(mode="python")),
        )
    except ValidationError as exc:
        raise PolicyViolation("review_append_denied", "Review append is not authorized.") from exc


def _seal_authorization(
    draft: TrustedReviewAuthorization,
) -> TrustedReviewAuthorization:
    payload = draft.model_dump(mode="python")
    payload["receipt_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"receipt_sha256"})
    )
    return TrustedReviewAuthorization.model_validate(payload)


def _seal_event(draft: ReviewAppend) -> ReviewAppend:
    payload = draft.model_dump(mode="python")
    payload["event_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"event_sha256"})
    )
    return ReviewAppend.model_validate(payload)
