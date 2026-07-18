from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO

from ynoy.constants import CODEX_INGEST_MAX_LINE_BYTES
from ynoy.errors import DataValidationError


@dataclass(frozen=True, slots=True)
class RawJsonlRecord:
    byte_start: int
    byte_length: int
    line_number: int
    record_sha256: str
    payload: bytes | None
    oversized: bool


def iter_jsonl_records(
    stream: BinaryIO,
    *,
    start_offset: int = 0,
    completed_lines: int = 0,
    max_line_bytes: int = CODEX_INGEST_MAX_LINE_BYTES,
) -> Iterator[RawJsonlRecord]:
    if start_offset < 0 or completed_lines < 0 or max_line_bytes < 1:
        raise DataValidationError(
            "codex_ingest_checkpoint_invalid", "Codex ingestion checkpoint is invalid."
        )
    stream.seek(start_offset)
    line_number = completed_lines
    while True:
        byte_start = stream.tell()
        prefix = stream.readline(max_line_bytes + 1)
        if not prefix:
            break
        line_number += 1
        yield _finish_record(stream, prefix, byte_start, line_number, max_line_bytes)


def _finish_record(
    stream: BinaryIO,
    prefix: bytes,
    byte_start: int,
    line_number: int,
    max_line_bytes: int,
) -> RawJsonlRecord:
    digest = hashlib.sha256(prefix)
    length = len(prefix)
    oversized = length > max_line_bytes
    ended = prefix.endswith(b"\n")
    while not ended:
        chunk = stream.readline(max_line_bytes + 1)
        if not chunk:
            break
        digest.update(chunk)
        length += len(chunk)
        oversized = oversized or length > max_line_bytes
        ended = chunk.endswith(b"\n")
    return RawJsonlRecord(
        byte_start=byte_start,
        byte_length=length,
        line_number=line_number,
        record_sha256=digest.hexdigest(),
        payload=None if oversized else prefix,
        oversized=oversized,
    )
