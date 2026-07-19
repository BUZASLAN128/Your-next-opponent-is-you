from __future__ import annotations

import hashlib
import os
from typing import BinaryIO

from ynoy.errors import DataValidationError
from ynoy.models.full_persona import FullCorpusSource


class VerifiedChunkStream:
    """Serve only bytes that match the frozen source chunk receipts."""

    def __init__(self, raw: BinaryIO, source: FullCorpusSource) -> None:
        self._raw = raw
        self._source = source
        self._position = 0
        self._chunk_index = -1
        self._chunk = b""

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence != os.SEEK_SET or offset < 0 or offset > self._source.file_bytes:
            raise DataValidationError(
                "full_persona_source_seek_invalid",
                "Verified source reads require a bounded absolute offset.",
            )
        self._position = offset
        return offset

    def tell(self) -> int:
        return self._position

    def readline(self, limit: int = -1) -> bytes:
        if limit < 1:
            raise DataValidationError(
                "full_persona_source_read_invalid",
                "Verified source reads require a positive byte bound.",
            )
        remaining = min(limit, self._source.file_bytes - self._position)
        parts: list[bytes] = []
        while remaining > 0:
            chunk = self._current_chunk()
            local = self._position % self._source.chunk_size_bytes
            segment = chunk[local : local + remaining]
            newline = segment.find(b"\n")
            if newline >= 0:
                segment = segment[: newline + 1]
            if not segment:
                _chunk_error()
            parts.append(segment)
            consumed = len(segment)
            self._position += consumed
            remaining -= consumed
            if newline >= 0:
                break
        return b"".join(parts)

    def _current_chunk(self) -> bytes:
        index = self._position // self._source.chunk_size_bytes
        if index != self._chunk_index:
            self._chunk = _read_verified_chunk(self._raw, self._source, index)
            self._chunk_index = index
        return self._chunk


def _read_verified_chunk(raw: BinaryIO, source: FullCorpusSource, chunk_index: int) -> bytes:
    if chunk_index < 0 or chunk_index >= len(source.chunk_sha256):
        _chunk_error()
    start = chunk_index * source.chunk_size_bytes
    expected_bytes = min(source.chunk_size_bytes, source.file_bytes - start)
    raw.seek(start)
    value = raw.read(expected_bytes)
    if (
        len(value) != expected_bytes
        or hashlib.sha256(value).hexdigest() != source.chunk_sha256[chunk_index]
    ):
        _chunk_error()
    return value


def _chunk_error() -> None:
    raise DataValidationError(
        "full_persona_source_chunk_changed",
        "A frozen full-persona source chunk changed before it could be consumed.",
    )
