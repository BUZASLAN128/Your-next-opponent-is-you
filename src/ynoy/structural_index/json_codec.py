from __future__ import annotations

import json
import math

from .validation import (
    MAX_STORED_JSON_DEPTH,
    MAX_STORED_JSON_VALUES,
    input_error,
    integrity_error,
)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise input_error("value is not strict JSON") from exc


def strict_json_object(content: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        _validate_loaded_json(value)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise integrity_error("stored JSON is malformed or non-finite") from exc
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return value
    raise integrity_error("stored JSON root must be an object")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _validate_loaded_json(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    visited = 0
    while stack:
        item, depth = stack.pop()
        visited += 1
        if visited > MAX_STORED_JSON_VALUES or depth > MAX_STORED_JSON_DEPTH:
            raise ValueError("stored JSON exceeds structural limits")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("stored JSON contains a non-finite number")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
