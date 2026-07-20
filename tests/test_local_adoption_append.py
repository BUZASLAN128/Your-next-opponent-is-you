from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.formal_runtime import POLICY_VERSION
from test_local_adoption import FakeSshRunner, _auth, _issue

from ynoy.errors import PolicyViolation
from ynoy.review_append import (
    InMemoryReviewAppendStore,
    build_review_append,
    build_review_authorization,
)
from ynoy.util import new_id


def _authorization():
    return build_review_authorization(
        actor_id="local-user",
        subject_id="self",
        review_sha256="7" * 64,
        stream_id="review:self",
        allowed_event_types=("claim_adopted",),
        policy_version=POLICY_VERSION,
    )


def _event(authorization, adoption, *, payload_sha256: str = "8" * 64):
    return build_review_append(
        event_id=new_id(),
        stream_id="review:self",
        expected_revision=0,
        event_type="claim_adopted",
        payload_sha256=payload_sha256,
        causation_id=new_id(),
        authorization=authorization,
        adoption=adoption,
    )


def test_review_append_accepts_verified_local_adoption(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    authenticator = _auth(tmp_path / "auth", runner, lambda: now)
    adoption = authenticator.verify(_issue(authenticator), b"valid-signature")
    authorization = _authorization()
    store = InMemoryReviewAppendStore(
        policy_version=POLICY_VERSION,
        adoption_verifier=authenticator,
    )

    ack = store.append(
        _event(authorization, adoption), adoption=adoption, authorization=authorization
    )

    assert ack.revision == 1
    assert store.head("review:self") == 1


def test_review_append_rejects_foreign_receipt_and_event_binding(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    first = _auth(tmp_path / "first", FakeSshRunner(), lambda: now)
    foreign = _auth(tmp_path / "foreign", FakeSshRunner(), lambda: now)
    adoption = foreign.verify(_issue(foreign), b"valid-signature")
    authorization = _authorization()
    store = InMemoryReviewAppendStore(
        policy_version=POLICY_VERSION,
        adoption_verifier=first,
    )

    with pytest.raises(PolicyViolation, match=r"authorized|denied"):
        store.append(
            _event(authorization, adoption), adoption=adoption, authorization=authorization
        )

    local = first.verify(_issue(first), b"valid-signature")
    with pytest.raises(PolicyViolation, match=r"authorized|denied"):
        store.append(
            _event(authorization, local, payload_sha256="c" * 64),
            adoption=local,
            authorization=authorization,
        )
