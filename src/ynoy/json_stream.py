from __future__ import annotations

import codecs
import json
from collections.abc import Iterator
from io import StringIO
from typing import IO, Any

from ynoy.constants import DEFAULT_ARCHIVE_MAX_JSON_ITEM_BYTES, DEFAULT_JSON_MAX_NESTING
from ynoy.errors import DataValidationError


class JsonObjectArrayParser:
    def __init__(self, max_item_bytes: int, max_nesting: int):
        self.max_item_bytes = max_item_bytes
        self.max_nesting = max_nesting
        self.started = False
        self.ended = False
        self.collecting = False
        self.expect_value = True
        self.depth = 0
        self.in_string = False
        self.escaped = False
        self.item_buffer = StringIO()
        self.item_size = 0

    def feed(self, text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for character in text:
            item = self._consume(character)
            if item is not None:
                items.append(item)
        return items

    def finish(self) -> None:
        if self.collecting or not self.started or not self.ended:
            raise DataValidationError(
                "json_truncated",
                "Conversation JSON ended before the top-level array was complete.",
            )

    def _consume(self, character: str) -> dict[str, Any] | None:
        if self.ended:
            if not character.isspace():
                raise DataValidationError(
                    "json_trailing_content", "Conversation JSON has trailing content."
                )
            return None
        if not self.started:
            self._start_array(character)
            return None
        if not self.collecting:
            self._consume_separator(character)
            return None
        return self._consume_item(character)

    def _start_array(self, character: str) -> None:
        if character.isspace():
            return
        if character != "[":
            raise DataValidationError(
                "json_array_required", "Conversation JSON must be a top-level array."
            )
        self.started = True
        self.expect_value = True

    def _consume_separator(self, character: str) -> None:
        if character.isspace():
            return
        if self.expect_value:
            if character == "]":
                self.ended = True
                return
            if character != "{":
                raise DataValidationError(
                    "json_object_required", "Every conversation array item must be an object."
                )
            self._begin_item(character)
            return
        if character == ",":
            self.expect_value = True
            return
        if character == "]":
            self.ended = True
            return
        raise DataValidationError(
            "json_separator_invalid", "Conversation JSON has an invalid separator."
        )

    def _begin_item(self, character: str) -> None:
        self.collecting = True
        self.depth = 1
        self.in_string = False
        self.escaped = False
        self.item_buffer = StringIO()
        self.item_buffer.write(character)
        self.item_size = 1

    def _consume_item(self, character: str) -> dict[str, Any] | None:
        self.item_buffer.write(character)
        self.item_size += len(character.encode("utf-8"))
        if self.item_size > self.max_item_bytes:
            raise DataValidationError(
                "json_item_limit",
                "A single conversation exceeds the configured item limit.",
                details={"limit": self.max_item_bytes},
            )
        if self.in_string:
            self._consume_string_character(character)
            return None
        if character == '"':
            self.in_string = True
        elif character in "[{":
            self.depth += 1
            if self.depth > self.max_nesting:
                raise DataValidationError(
                    "json_nesting_limit",
                    "Conversation JSON exceeds the configured nesting limit.",
                    details={"limit": self.max_nesting},
                )
        elif character in "]}":
            self.depth -= 1
            if self.depth == 0:
                return self._finish_item()
        return None

    def _consume_string_character(self, character: str) -> None:
        if self.escaped:
            self.escaped = False
        elif character == "\\":
            self.escaped = True
        elif character == '"':
            self.in_string = False

    def _finish_item(self) -> dict[str, Any]:
        try:
            item = json.loads(self.item_buffer.getvalue())
        except json.JSONDecodeError as exc:
            raise DataValidationError(
                "json_item_invalid", "A conversation object is invalid JSON."
            ) from exc
        if not isinstance(item, dict):
            raise DataValidationError(
                "json_object_required", "Every conversation array item must be an object."
            )
        self.collecting = False
        self.expect_value = False
        self.item_buffer = StringIO()
        self.item_size = 0
        return item


def _decoded_chunks(stream: IO[bytes], chunk_size: int) -> Iterator[str]:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        while raw := stream.read(chunk_size):
            yield decoder.decode(raw, final=False)
        tail = decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise DataValidationError(
            "json_utf8_invalid", "Conversation JSON is not valid UTF-8."
        ) from exc
    if tail:
        yield tail


def iter_json_object_array(
    stream: IO[bytes],
    *,
    max_item_bytes: int = DEFAULT_ARCHIVE_MAX_JSON_ITEM_BYTES,
    max_nesting: int = DEFAULT_JSON_MAX_NESTING,
    chunk_size: int = 1024 * 1024,
) -> Iterator[dict[str, Any]]:
    parser = JsonObjectArrayParser(max_item_bytes, max_nesting)
    for chunk in _decoded_chunks(stream, chunk_size):
        yield from parser.feed(chunk)
    parser.finish()
