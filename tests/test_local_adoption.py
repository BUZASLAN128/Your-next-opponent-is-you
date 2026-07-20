from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from support.formal_decisions import admitted_claim

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.local_adoption import LocalSshAdoptionAuthenticator
from ynoy.util import new_id


class FakeSshRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, bytes, str, str]] = []

    def verify(self, payload: bytes, signature: bytes, *, actor_id: str, public_key: str) -> bool:
        self.calls.append((payload, signature, actor_id, public_key))
        return signature == b"valid-signature"


def _auth(
    root: Path,
    runner: FakeSshRunner,
    now: Callable[[], datetime],
) -> LocalSshAdoptionAuthenticator:
    auth = LocalSshAdoptionAuthenticator(root=root, runner=runner, now=now)
    auth.enroll_public_key(
        actor_id="local-user",
        public_key=(
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA "
            "ynoy-test"
        ),
    )
    return auth


def _issue(auth: LocalSshAdoptionAuthenticator, *, expires_at: datetime | None = None):
    return auth.issue(
        admitted_claim(),
        review_sha256="7" * 64,
        expected_head=0,
        actor_id="local-user",
        stream_id="review:self",
        event_type="claim_adopted",
        payload_sha256="8" * 64,
        expires_at=expires_at,
    )


def test_ssh_signature_is_bound_and_one_time_across_restart(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    first = _auth(tmp_path, runner, lambda: now)
    challenge = _issue(first, expires_at=now + timedelta(minutes=5))

    receipt = first.verify(challenge, b"valid-signature")
    assert first.validate(receipt)
    assert runner.calls and runner.calls[0][1] == b"valid-signature"

    with pytest.raises(PolicyViolation, match=r"replay|used|invalid"):
        first.verify(challenge, b"valid-signature")
    restarted = _auth(tmp_path, runner, lambda: now)
    with pytest.raises(PolicyViolation, match=r"replay|used|invalid"):
        restarted.verify(challenge, b"valid-signature")


def test_enrollment_is_required_idempotent_and_not_replaceable(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    auth = LocalSshAdoptionAuthenticator(root=tmp_path, runner=runner, now=lambda: now)
    with pytest.raises(PolicyViolation, match=r"enroll|credential|key"):
        _issue(auth)

    key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA ynoy-test"
    auth.enroll_public_key(actor_id="local-user", public_key=key)
    auth.enroll_public_key(actor_id="local-user", public_key=key)
    with pytest.raises(PolicyViolation, match=r"replace|credential|key"):
        auth.enroll_public_key(
            actor_id="local-user",
            public_key=(
                "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA "
                "ynoy-test"
            ),
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("subject_id", "other-subject"),
        ("review_sha256", "9" * 64),
        ("claim_id", new_id()),
        ("expected_head", 1),
        ("actor_id", "other-actor"),
        ("stream_id", "review:other"),
        ("event_type", "other-event"),
        ("payload_sha256", "a" * 64),
    ),
    ids=("subject", "review", "claim", "head", "actor", "stream", "event", "payload"),
)
def test_ssh_challenge_rejects_rebound_context(
    tmp_path: Path, field: str, replacement: object
) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    auth = _auth(tmp_path, runner, lambda: now)
    challenge = _issue(auth, expires_at=now + timedelta(minutes=5))

    rebound = challenge.model_copy(update={field: replacement})
    with pytest.raises(PolicyViolation, match=r"invalid|binding|replay"):
        auth.verify(rebound, b"valid-signature")


def test_ssh_authenticator_rejects_bad_signature_and_expired_challenge(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    auth = _auth(tmp_path, runner, lambda: now)
    challenge = _issue(auth, expires_at=now + timedelta(seconds=1))

    with pytest.raises(PolicyViolation, match=r"signature|invalid"):
        auth.verify(challenge, b"bad-signature")

    expired = _auth(tmp_path, runner, lambda: now + timedelta(seconds=2))
    with pytest.raises(PolicyViolation, match=r"expir|invalid"):
        expired.verify(challenge, b"valid-signature")


def test_issue_rejects_expiry_beyond_five_minutes_and_exact_expiry_is_closed(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    auth = _auth(tmp_path, runner, lambda: now)

    with pytest.raises(PolicyViolation, match=r"expir|ttl|window|lifetime"):
        _issue(auth, expires_at=now + timedelta(minutes=5, seconds=1))

    exact_clock = [now]
    exact = _auth(tmp_path / "exact", runner, lambda: exact_clock[0])
    challenge = _issue(exact, expires_at=now + timedelta(minutes=5))
    exact_clock[0] = challenge.expires_at
    with pytest.raises(PolicyViolation, match=r"expir|invalid"):
        exact.verify(challenge, b"valid-signature")


def test_state_status_other_than_pending_or_used_is_rejected(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    auth = _auth(tmp_path, runner, lambda: now)
    challenge = _issue(auth)
    state_path = auth.states / f"{challenge.challenge_id}.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["status"] = "revoked"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises((PolicyViolation, DataValidationError)) as blocked:
        auth.verify(challenge, b"valid-signature")

    assert "invalid" in str(blocked.value).casefold()


def test_validate_rejects_receipt_when_enrolled_profile_fingerprint_changes(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    runner = FakeSshRunner()
    auth = _auth(tmp_path, runner, lambda: now)
    receipt = auth.verify(_issue(auth), b"valid-signature")
    profile_path = auth.root / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["credential_fingerprint"] = "f" * 64
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    assert auth.validate(receipt) is False
