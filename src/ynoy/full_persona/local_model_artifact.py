from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from ynoy.errors import DataValidationError


def verify_local_model_artifact(path: Path, expected_sha256: str, *, prefix: str) -> None:
    resolved = path.expanduser().resolve()
    if path.is_symlink() or not resolved.is_file():
        raise DataValidationError(
            f"{prefix}_artifact_invalid", "The local model artifact must be a regular file."
        )
    digest = sha256()
    with resolved.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise DataValidationError(
            f"{prefix}_artifact_mismatch", "The local model artifact hash does not match."
        )
