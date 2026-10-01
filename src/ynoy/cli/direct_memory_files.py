from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ynoy.cli.context import CommandContext
from ynoy.direct_memory.codec import strict_loads
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.policy import assert_outside_git, require_private_source

MAX_INPUT_BYTES = 64 * 1024 * 1024


def load_input(value: str, context: CommandContext, *, synthetic: bool) -> object:
    path = Path(value)
    if not synthetic:
        path = require_private_source(path, context.settings.require_private_root())
    require_regular_file(path)
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise ValueError("input too large")
        return strict_loads(content.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise DataValidationError(
            "direct_memory_input_invalid", "Input JSON could not be read."
        ) from exc


def load_model[Model: BaseModel](value: object, model: type[Model]) -> Model:
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise DataValidationError(
            "direct_memory_input_invalid", "Input failed typed validation."
        ) from exc


def output_path(value: str, context: CommandContext) -> Path:
    path = Path(value).expanduser().resolve()
    root = context.settings.require_private_root().expanduser().resolve()
    assert_outside_git(path)
    if not path.is_relative_to(root):
        raise PolicyViolation(
            "direct_memory_output_outside_root", "Output must stay in the private root."
        )
    reject_link_if_present(path)
    reject_link_if_present(path.parent)
    if path.exists():
        raise DataValidationError(
            "direct_memory_output_exists", "Output must use a new destination."
        )
    return path


def cutoff(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DataValidationError(
            "direct_memory_time_invalid", "Cutoff must be an ISO timestamp."
        ) from exc
    if parsed.utcoffset() is None:
        raise DataValidationError("direct_memory_time_invalid", "Cutoff must include a timezone.")
    return parsed
