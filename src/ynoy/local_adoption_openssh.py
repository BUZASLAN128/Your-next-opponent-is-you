from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from ynoy.errors import PolicyViolation
from ynoy.persona_study.storage_paths import require_regular_file


class SshSignatureRunner(Protocol):
    def verify(
        self, payload: bytes, signature: bytes, *, actor_id: str, public_key: str
    ) -> bool: ...


class OpenSshSignatureRunner:
    """Invoke the system OpenSSH signer without exposing key material to YNOY."""

    def __init__(self, executable: Path | None = None) -> None:
        self.executable = executable or Path(r"C:\Windows\System32\OpenSSH\ssh-keygen.exe")

    @property
    def available(self) -> bool:
        return self.executable.is_file()

    def enroll(self, key_path: Path) -> str:
        """Create one passphrase-protected Ed25519 key through the OpenSSH console UI."""
        self._require_executable()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists() or key_path.with_suffix(".pub").exists():
            raise PolicyViolation(
                "local_authenticator_key_exists", "Refusing to overwrite an adoption key."
            )
        result = subprocess.run(
            [
                str(self.executable),
                "-t",
                "ed25519",
                "-a",
                "64",
                "-f",
                str(key_path),
                "-C",
                "ynoy-local-adoption",
            ],
            check=False,
            timeout=300,
        )
        if result.returncode != 0 or not key_path.with_suffix(".pub").is_file():
            raise PolicyViolation(
                "local_authenticator_enrollment_failed", "OpenSSH key enrollment failed."
            )
        if self._accepts_empty_passphrase(key_path):
            raise PolicyViolation(
                "local_authenticator_passphrase_required",
                "The local adoption key must use a non-empty passphrase.",
            )
        return key_path.with_suffix(".pub").read_text(encoding="utf-8").strip()

    def sign(self, payload: bytes, key_path: Path) -> bytes:
        """Ask OpenSSH for the key passphrase and sign the exact canonical payload."""
        self._require_executable()
        require_regular_file(key_path)
        with tempfile.TemporaryDirectory(prefix="ynoy-adoption-sign-") as raw:
            payload_path = Path(raw) / "challenge.json"
            payload_path.write_bytes(payload)
            result = subprocess.run(
                [
                    str(self.executable),
                    "-Y",
                    "sign",
                    "-f",
                    str(key_path),
                    "-n",
                    "ynoy-adoption",
                    str(payload_path),
                ],
                check=False,
                timeout=300,
            )
            signature_path = payload_path.with_suffix(".json.sig")
            if result.returncode != 0 or not signature_path.is_file():
                raise PolicyViolation(
                    "local_adoption_signing_failed", "The adoption signature was not created."
                )
            signature = signature_path.read_bytes()
        return signature

    def verify(self, payload: bytes, signature: bytes, *, actor_id: str, public_key: str) -> bool:
        self._require_executable()
        validate_actor(actor_id)
        validate_public_key(public_key)
        with tempfile.TemporaryDirectory(prefix="ynoy-adoption-verify-") as raw:
            root = Path(raw)
            signature_path = root / "challenge.sig"
            signers_path = root / "allowed_signers"
            signature_path.write_bytes(signature)
            signers_path.write_text(f"{actor_id} {public_key}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    str(self.executable),
                    "-Y",
                    "verify",
                    "-f",
                    str(signers_path),
                    "-I",
                    actor_id,
                    "-n",
                    "ynoy-adoption",
                    "-s",
                    str(signature_path),
                ],
                input=payload,
                capture_output=True,
                check=False,
                timeout=30,
            )
        return result.returncode == 0

    def _accepts_empty_passphrase(self, key_path: Path) -> bool:
        result = subprocess.run(
            [str(self.executable), "-y", "-P", "", "-f", str(key_path)],
            capture_output=True,
            check=False,
            timeout=30,
        )
        return result.returncode == 0

    def _require_executable(self) -> None:
        if not self.executable.is_file():
            raise PolicyViolation(
                "local_authenticator_openssh_missing", "The system OpenSSH signer is unavailable."
            )


def validate_actor(actor_id: str) -> None:
    if not actor_id or actor_id != actor_id.strip() or any(char.isspace() for char in actor_id):
        raise PolicyViolation("local_adoption_actor_invalid", "The adoption actor is invalid.")


def validate_public_key(public_key: str) -> None:
    if (
        public_key != public_key.strip()
        or "\n" in public_key
        or "\r" in public_key
        or not public_key.startswith(("ssh-ed25519 ", "ecdsa-sha2-nistp256 "))
    ):
        raise PolicyViolation("local_adoption_public_key_invalid", "The public key is invalid.")
