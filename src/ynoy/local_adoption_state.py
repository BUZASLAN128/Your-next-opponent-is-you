from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models.local_adoption import (
    LocalAdoptionChallenge,
    LocalAuthenticatorProfile,
    VerifiedLocalAdoption,
)
from ynoy.persona_study.storage_paths import require_regular_file
from ynoy.util import canonical_sha256

_MAX_CONTROL_BYTES = 128 * 1024


def read_profile(root: Path, *, required: bool) -> LocalAuthenticatorProfile | None:
    path = root / "profile.json"
    if not path.exists():
        if required:
            raise PolicyViolation(
                "local_authenticator_not_enrolled",
                "Enroll an independent local signing key before adopting persona state.",
            )
        return None
    try:
        return LocalAuthenticatorProfile.model_validate_json(_read_bounded(path))
    except (OSError, ValidationError) as exc:
        raise DataValidationError(
            "local_authenticator_profile_invalid", "The local authenticator profile is invalid."
        ) from exc


def read_state(
    states: Path, challenge_id: object
) -> tuple[LocalAdoptionChallenge, VerifiedLocalAdoption | None, str]:
    try:
        value = json.loads(_read_bounded(state_path(states, challenge_id)))
        if value.get("status") not in {"pending", "used"}:
            raise ValueError("invalid state status")
        challenge = LocalAdoptionChallenge.model_validate(value["challenge"])
        receipt_value = value.get("receipt")
        if (value["status"] == "used") != (receipt_value is not None):
            raise ValueError("state receipt does not match status")
        receipt = VerifiedLocalAdoption.model_validate(receipt_value) if receipt_value else None
        profile_sha256 = str(value["profile_sha256"])
        expected = canonical_sha256(
            {key: item for key, item in value.items() if key != "state_sha256"}
        )
        if value.get("state_sha256") != expected:
            raise ValueError("state digest mismatch")
    except (KeyError, TypeError, ValueError, OSError, ValidationError) as exc:
        raise DataValidationError(
            "local_adoption_state_invalid", "The local adoption state is invalid."
        ) from exc
    return challenge, receipt, profile_sha256


def sealed_state(
    status: str,
    challenge: LocalAdoptionChallenge,
    receipt: VerifiedLocalAdoption | None,
    profile_sha256: str,
) -> dict[str, object]:
    state: dict[str, object] = {
        "status": status,
        "challenge": challenge.model_dump(mode="json"),
        "receipt": receipt.model_dump(mode="json") if receipt is not None else None,
        "profile_sha256": profile_sha256,
    }
    state["state_sha256"] = canonical_sha256(state)
    return state


def state_path(states: Path, challenge_id: object) -> Path:
    return states / f"{challenge_id}.json"


def sealed[ModelT: BaseModel](
    model: type[ModelT], payload: dict[str, object], field: str
) -> ModelT:
    draft = cast(Any, model).model_construct(**payload, **{field: "0" * 64})
    normalized = draft.model_dump(mode="json", exclude={field})
    normalized[field] = canonical_sha256(normalized)
    return model.model_validate(normalized)


def _read_bounded(path: Path) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        value = stream.read(_MAX_CONTROL_BYTES + 1)
    if len(value) > _MAX_CONTROL_BYTES:
        raise DataValidationError("local_adoption_state_oversized", "Adoption state is oversized.")
    return value
