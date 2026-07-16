from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from ynoy.constants import DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES
from ynoy.errors import DataValidationError
from ynoy.models import ClaimReviewDecision

_DECISION_ADAPTER: TypeAdapter[list[ClaimReviewDecision]] = TypeAdapter(list[ClaimReviewDecision])


def load_review_model[T: BaseModel](path: Path, model_type: type[T], *, label: str) -> T:
    """Load one bounded strict JSON model from an already authorized path."""
    raw = _load_json(path, label=label)
    try:
        return model_type.model_validate(raw)
    except ValidationError as exc:
        raise DataValidationError(
            f"{label}_invalid", f"The {label.replace('_', ' ')} failed strict validation."
        ) from exc


def load_review_decisions(path: Path) -> tuple[ClaimReviewDecision, ...]:
    raw = _load_json(path, label="review_decisions")
    try:
        decisions = tuple(_DECISION_ADAPTER.validate_python(raw))
    except ValidationError as exc:
        raise DataValidationError(
            "review_decisions_invalid", "Review decisions failed strict validation."
        ) from exc
    if not decisions:
        raise DataValidationError(
            "review_decisions_required", "At least one explicit claim decision is required."
        )
    return decisions


def _load_json(path: Path, *, label: str) -> Any:
    try:
        source = path.expanduser().resolve(strict=True)
        if not source.is_file():
            raise DataValidationError(f"{label}_not_file", "Review input must be a file.")
        if source.suffix.casefold() != ".json":
            raise DataValidationError(f"{label}_json_required", "Review input must be JSON.")
        if source.stat().st_size > DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES:
            raise DataValidationError(
                f"{label}_too_large",
                "Review input exceeds the configured byte limit.",
                details={"limit": DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES},
            )
        with source.open("rb") as handle:
            raw = handle.read(DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES + 1)
    except DataValidationError:
        raise
    except OSError as exc:
        raise DataValidationError(f"{label}_unreadable", "Review input is unreadable.") from exc
    if len(raw) > DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES:
        raise DataValidationError(
            f"{label}_too_large", "Review input grew beyond the configured byte limit."
        )
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            f"{label}_invalid", "Review input is not valid UTF-8 JSON."
        ) from exc
