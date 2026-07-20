from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError
from support.formal_runtime import POLICY_VERSION, REVIEW_SHA256, runtime_fixture

from ynoy.adoption import adoption_matches
from ynoy.errors import PolicyViolation
from ynoy.models import DataClass
from ynoy.models.formal_decision import DecisionGroupKey
from ynoy.models.formal_runtime import TrustedReviewAuthorization
from ynoy.models.review_vocab import TargetLayer
from ynoy.review_append import build_review_authorization
from ynoy.util import new_id


def _attempt_append(fixture, event) -> str:
    try:
        fixture.store.append(
            event,
            adoption=fixture.adoption,
            authorization=fixture.authorization,
        )
    except PolicyViolation as error:
        return error.code
    return "committed"


def _rebound_authorization(fixture, **updates) -> TrustedReviewAuthorization:
    values = {
        "actor_id": fixture.authorization.actor_id,
        "subject_id": fixture.authorization.subject_id,
        "review_sha256": fixture.authorization.review_sha256,
        "stream_id": fixture.authorization.stream_id,
        "allowed_event_types": fixture.authorization.allowed_event_types,
        "policy_version": fixture.authorization.policy_version,
        **updates,
    }
    return build_review_authorization(**values)


def test_adoption_is_bound_and_not_replayable() -> None:
    fixture = runtime_fixture()
    challenge = fixture.verifier.issue(
        fixture.claim,
        review_sha256=REVIEW_SHA256,
        expected_head=0,
    )
    fixture.verifier.verify(challenge, response_sha256="a" * 64)

    with pytest.raises(PolicyViolation, match="invalid"):
        fixture.verifier.verify(challenge, response_sha256="a" * 64)
    assert adoption_matches(
        fixture.adoption,
        fixture.claim,
        review_sha256=REVIEW_SHA256,
        expected_head=0,
    )
    assert not adoption_matches(
        fixture.adoption,
        fixture.claim,
        review_sha256="b" * 64,
        expected_head=0,
    )
    with pytest.raises(PolicyViolation) as blocked:
        fixture.verifier.issue(
            fixture.claim,
            review_sha256=REVIEW_SHA256,
            expected_head=0,
            data_class=DataClass.DERIVED_IDENTITY,
        )
    assert blocked.value.code == "real_adoption_authenticator_unavailable"


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("subject_id", "another-subject"),
        ("review_sha256", "b" * 64),
        ("claim_id", new_id()),
        (
            "full_key",
            DecisionGroupKey(
                subject_id="self",
                target_layer=TargetLayer.SCOPED_POLICY,
                reviewed_decision_key="another-decision",
            ),
        ),
        ("expected_head", 1),
        ("channel_id", "another-channel"),
    ),
    ids=("subject", "review", "claim", "decision-key", "head", "channel"),
)
def test_adoption_challenge_rejects_every_rebound_binding(field: str, replacement: object) -> None:
    fixture = runtime_fixture()
    challenge = fixture.verifier.issue(
        fixture.claim,
        review_sha256=REVIEW_SHA256,
        expected_head=0,
    )
    rebound = challenge.model_copy(update={field: replacement})

    with pytest.raises(PolicyViolation) as blocked:
        fixture.verifier.verify(rebound, response_sha256="a" * 64)

    assert blocked.value.code == "adoption_challenge_invalid"
    assert fixture.verifier.validate(fixture.adoption)


@pytest.mark.parametrize(
    "data_class", tuple(item for item in DataClass if item != DataClass.PUBLIC_SYNTHETIC)
)
def test_model_or_private_data_cannot_authenticate_adoption(data_class: DataClass) -> None:
    fixture = runtime_fixture()

    with pytest.raises(PolicyViolation) as blocked:
        fixture.verifier.issue(
            fixture.claim,
            review_sha256=REVIEW_SHA256,
            expected_head=0,
            data_class=data_class,
        )

    assert blocked.value.code == "real_adoption_authenticator_unavailable"


def test_concurrent_append_has_one_winner_and_retry_is_idempotent() -> None:
    fixture = runtime_fixture()
    first = fixture.event()
    second = fixture.event()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            executor.map(lambda event: _attempt_append(fixture, event), (first, second))
        )

    assert sorted(outcomes) == ["committed", "review_append_head_mismatch"]
    winner = first if outcomes[0] == "committed" else second
    retry = fixture.store.append(
        winner,
        adoption=fixture.adoption,
        authorization=fixture.authorization,
    )
    assert retry.idempotent_replay and fixture.store.head(winner.stream_id) == 1
    rebound = fixture.event(event_id=winner.event_id, payload_sha256="c" * 64)
    with pytest.raises(PolicyViolation) as blocked:
        fixture.store.append(
            rebound,
            adoption=fixture.adoption,
            authorization=fixture.authorization,
        )
    assert blocked.value.code == "review_append_denied"


def test_append_rejects_stale_future_and_rebound_event() -> None:
    fixture = runtime_fixture()
    committed = fixture.event()
    fixture.store.append(
        committed,
        adoption=fixture.adoption,
        authorization=fixture.authorization,
    )
    for revision in (0, 2):
        with pytest.raises(PolicyViolation):
            fixture.store.append(
                fixture.event(expected_revision=revision),
                adoption=fixture.adoption,
                authorization=fixture.authorization,
            )
    rebound = fixture.event(event_id=committed.event_id, stream_id="review:other")
    with pytest.raises(PolicyViolation) as blocked:
        fixture.store.append(
            rebound,
            adoption=fixture.adoption,
            authorization=fixture.authorization,
        )
    assert blocked.value.code == "review_append_denied"


def test_review_append_requires_trusted_bound_authorization_context() -> None:
    fixture = runtime_fixture()
    event = fixture.event()
    intruder = _rebound_authorization(fixture, actor_id="intruder")
    with pytest.raises(PolicyViolation) as blocked:
        fixture.store.append(event, adoption=fixture.adoption, authorization=intruder)
    assert blocked.value.code == "review_append_denied"
    with pytest.raises(ValidationError):
        TrustedReviewAuthorization.model_validate(
            {**fixture.authorization.model_dump(mode="python"), "authenticated": False}
        )


def test_review_append_retry_binds_actor_subject_review_and_adoption_context() -> None:
    fixture = runtime_fixture()
    event = fixture.event()
    fixture.store.append(
        event,
        adoption=fixture.adoption,
        authorization=fixture.authorization,
    )
    fixture.store.policy_version = "formal-policy/2"
    retry = fixture.store.append(
        event,
        adoption=fixture.adoption,
        authorization=fixture.authorization,
    )
    assert retry.idempotent_replay and retry.content is None
    with pytest.raises(PolicyViolation):
        fixture.store.append(
            fixture.event(expected_revision=1),
            adoption=fixture.adoption,
            authorization=fixture.authorization,
        )
    rebound = _rebound_authorization(fixture, policy_version=POLICY_VERSION, actor_id="other")
    with pytest.raises(PolicyViolation) as blocked:
        fixture.store.append(event, adoption=fixture.adoption, authorization=rebound)
    assert blocked.value.code == "review_append_denied"
