from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.full_persona.run_lock import exclusive_run_lock
from ynoy.local_adoption_openssh import (
    OpenSshSignatureRunner,
    SshSignatureRunner,
    validate_actor,
    validate_public_key,
)
from ynoy.local_adoption_state import read_profile as _read_profile
from ynoy.local_adoption_state import read_state as _read_state
from ynoy.local_adoption_state import sealed as _sealed
from ynoy.local_adoption_state import sealed_state as _sealed_state
from ynoy.local_adoption_state import state_path as _state_path
from ynoy.models.formal_decision import AdmittedDecisionClaim
from ynoy.models.local_adoption import (
    LocalAdoptionChallenge,
    LocalAuthenticatorProfile,
    VerifiedLocalAdoption,
)
from ynoy.persona_study.storage_paths import reject_link_if_present
from ynoy.policy import require_private_root
from ynoy.util import (
    atomic_write_bytes,
    canonical_json_bytes,
    new_id,
    sha256_bytes,
    utc_now,
)

_MAX_SIGNATURE_BYTES = 64 * 1024
_DEFAULT_TTL = timedelta(minutes=5)

__all__ = ["LocalSshAdoptionAuthenticator", "OpenSshSignatureRunner", "SshSignatureRunner"]


class LocalSshAdoptionAuthenticator:
    """Persist and verify exact adoption challenges signed outside the model runtime."""

    def __init__(
        self,
        *,
        root: Path,
        runner: SshSignatureRunner,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        assessment = require_private_root(root, real_data=True)
        self.root = assessment.root / "local-adoption-authenticator"
        self.runner = runner
        self.now = now
        self.states = self.root / "states"
        self.lock_path = self.root / "authenticator.lock"
        for path in (self.root, self.states):
            reject_link_if_present(path)

    @property
    def enrolled(self) -> bool:
        return _read_profile(self.root, required=False) is not None

    def enroll_with_system_openssh(self, *, actor_id: str) -> LocalAuthenticatorProfile:
        """Interactively enroll the independent key without accepting a model-supplied secret."""
        if not isinstance(self.runner, OpenSshSignatureRunner):
            raise PolicyViolation(
                "local_authenticator_runner_invalid", "System OpenSSH enrollment is unavailable."
            )
        if _read_profile(self.root, required=False) is not None:
            raise PolicyViolation(
                "local_authenticator_already_enrolled", "The local authenticator is enrolled."
            )
        public_key = self.runner.enroll(self.root / "identity")
        return self.enroll_public_key(actor_id=actor_id, public_key=public_key)

    def enroll_public_key(self, *, actor_id: str, public_key: str) -> LocalAuthenticatorProfile:
        """Bind one existing public key; replacement requires a separate recovery flow."""
        validate_actor(actor_id)
        validate_public_key(public_key)
        with exclusive_run_lock(self.lock_path):
            existing = _read_profile(self.root, required=False)
            if existing is not None:
                if (existing.actor_id, existing.public_key) != (actor_id, public_key):
                    raise PolicyViolation(
                        "local_authenticator_reenrollment_denied",
                        "The enrolled local adoption credential cannot be replaced implicitly.",
                    )
                return existing
            payload: dict[str, object] = {
                "protocol_version": "local-adoption-authenticator/0.1",
                "actor_id": actor_id,
                "public_key": public_key,
                "credential_fingerprint": sha256_bytes(public_key.encode("utf-8")),
                "signature_namespace": "ynoy-adoption",
                "enrolled_at": self.now(),
            }
            profile = _sealed(LocalAuthenticatorProfile, payload, "profile_sha256")
            self.root.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(
                self.root / "profile.json", canonical_json_bytes(profile.model_dump(mode="json"))
            )
            return profile

    def issue(
        self,
        claim: AdmittedDecisionClaim,
        *,
        review_sha256: str,
        expected_head: int,
        actor_id: str,
        stream_id: str,
        event_type: str,
        payload_sha256: str,
        expires_at: datetime | None = None,
    ) -> LocalAdoptionChallenge:
        profile = _read_profile(self.root, required=True)
        assert profile is not None
        if actor_id != profile.actor_id:
            raise PolicyViolation("local_adoption_actor_mismatch", "The adoption actor is invalid.")
        issued_at = self.now()
        challenge_expiry = _bounded_expiry(issued_at, expires_at)
        payload: dict[str, object] = {
            "protocol_version": "local-adoption-challenge/0.1",
            "challenge_id": new_id(),
            "actor_id": actor_id,
            "subject_id": claim.identity.subject_id,
            "review_sha256": review_sha256,
            "claim_id": claim.identity.claim_id,
            "claim_tuple_sha256": claim.identity.claim_tuple_sha256,
            "full_key": claim.identity.full_key,
            "expected_head": expected_head,
            "stream_id": stream_id,
            "event_type": event_type,
            "payload_sha256": payload_sha256,
            "channel_id": "local-openssh-passphrase/0.1",
            "credential_fingerprint": profile.credential_fingerprint,
            "issued_at": issued_at,
            "expires_at": challenge_expiry,
            "data_class": "D3",
        }
        challenge = _sealed(LocalAdoptionChallenge, payload, "challenge_sha256")
        state = _sealed_state("pending", challenge, None, profile.profile_sha256)
        with exclusive_run_lock(self.lock_path):
            self.states.mkdir(parents=True, exist_ok=True)
            path = _state_path(self.states, challenge.challenge_id)
            if path.exists():
                raise PolicyViolation(
                    "local_adoption_challenge_reused", "Challenge already exists."
                )
            atomic_write_bytes(path, canonical_json_bytes(state))
        return challenge

    def verify(self, challenge: LocalAdoptionChallenge, signature: bytes) -> VerifiedLocalAdoption:
        if not 0 < len(signature) <= _MAX_SIGNATURE_BYTES:
            raise PolicyViolation("local_adoption_signature_invalid", "Signature is invalid.")
        with exclusive_run_lock(self.lock_path):
            stored, receipt, profile_sha256 = _read_state(self.states, challenge.challenge_id)
            if receipt is not None or stored != challenge:
                raise PolicyViolation("local_adoption_replay", "Challenge is used or invalid.")
            if self.now() >= stored.expires_at:
                raise PolicyViolation("local_adoption_expired", "Challenge has expired.")
            profile = _read_profile(self.root, required=True)
            assert profile is not None
            if (
                profile.profile_sha256 != profile_sha256
                or profile.credential_fingerprint != stored.credential_fingerprint
            ):
                raise PolicyViolation(
                    "local_adoption_credential_mismatch", "The adoption credential is invalid."
                )
            payload = canonical_json_bytes(stored.model_dump(mode="json"))
            if not self.runner.verify(
                payload, signature, actor_id=stored.actor_id, public_key=profile.public_key
            ):
                raise PolicyViolation("local_adoption_signature_invalid", "Signature is invalid.")
            verified = self._receipt(stored, signature)
            state = _sealed_state("used", stored, verified, profile.profile_sha256)
            atomic_write_bytes(
                _state_path(self.states, stored.challenge_id), canonical_json_bytes(state)
            )
            return verified

    def approve(self, challenge: LocalAdoptionChallenge) -> VerifiedLocalAdoption:
        """Display the OpenSSH passphrase prompt, then consume the signed challenge once."""
        if not isinstance(self.runner, OpenSshSignatureRunner):
            raise PolicyViolation(
                "local_authenticator_runner_invalid", "Interactive OpenSSH approval is unavailable."
            )
        stored, receipt, _ = _read_state(self.states, challenge.challenge_id)
        if receipt is not None or stored != challenge or self.now() >= stored.expires_at:
            raise PolicyViolation("local_adoption_replay", "Challenge is used or invalid.")
        payload = canonical_json_bytes(stored.model_dump(mode="json"))
        signature = self.runner.sign(payload, self.root / "identity")
        return self.verify(stored, signature)

    def validate(self, receipt: VerifiedLocalAdoption) -> bool:
        try:
            profile = _read_profile(self.root, required=True)
            challenge, stored, profile_sha256 = _read_state(self.states, receipt.challenge_id)
        except (DataValidationError, PolicyViolation):
            return False
        assert profile is not None
        return bool(
            stored == receipt
            and profile.profile_sha256 == profile_sha256
            and profile.credential_fingerprint == receipt.credential_fingerprint
            and challenge.credential_fingerprint == receipt.credential_fingerprint
            and profile.actor_id == receipt.actor_id
        )

    def _receipt(
        self, challenge: LocalAdoptionChallenge, signature: bytes
    ) -> VerifiedLocalAdoption:
        payload: dict[str, object] = {
            "protocol_version": "verified-local-adoption/0.1",
            "adoption_id": new_id(),
            "challenge_id": challenge.challenge_id,
            "challenge_sha256": challenge.challenge_sha256,
            "actor_id": challenge.actor_id,
            "subject_id": challenge.subject_id,
            "review_sha256": challenge.review_sha256,
            "claim_id": challenge.claim_id,
            "claim_tuple_sha256": challenge.claim_tuple_sha256,
            "full_key": challenge.full_key,
            "expected_head": challenge.expected_head,
            "stream_id": challenge.stream_id,
            "event_type": challenge.event_type,
            "payload_sha256": challenge.payload_sha256,
            "channel_id": challenge.channel_id,
            "credential_fingerprint": challenge.credential_fingerprint,
            "signature_sha256": sha256_bytes(signature),
            "verified_at": self.now(),
            "data_class": challenge.data_class,
        }
        return _sealed(VerifiedLocalAdoption, payload, "receipt_sha256")


def _bounded_expiry(issued_at: datetime, expires_at: datetime | None) -> datetime:
    expiry = expires_at or issued_at + _DEFAULT_TTL
    if expiry > issued_at + _DEFAULT_TTL:
        raise PolicyViolation(
            "local_adoption_expiry_invalid",
            "The local adoption challenge cannot exceed the five-minute lifetime.",
        )
    return expiry
