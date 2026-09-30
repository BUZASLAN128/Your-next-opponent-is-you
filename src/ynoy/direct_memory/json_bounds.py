from __future__ import annotations

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_JSON_DEPTH = 128
MAX_JSON_ITEMS = 250_000


def check_json_bounds(value: str) -> None:
    """Bound encoded input before the JSON decoder allocates its object graph."""
    if len(value) > MAX_JSON_BYTES or len(value.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("JSON exceeds the byte limit")
    depth = 0
    items = 0
    quoted = False
    escaped = False
    for character in value:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            items += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON exceeds the nesting limit")
        elif character in "]}":
            depth -= 1
        elif character == ",":
            items += 1
        if items > MAX_JSON_ITEMS:
            raise ValueError("JSON exceeds the item limit")
