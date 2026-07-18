from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import BinaryIO

from ynoy.corpus.codex_raw_records import RawJsonlRecord
from ynoy.errors import DataValidationError


def iter_bounded_jsonl_records(
    stream: BinaryIO,
    *,
    start_offset: int = 0,
    completed_lines: int = 0,
    max_line_bytes: int,
    max_wire_record_bytes: int,
) -> Iterator[RawJsonlRecord]:
    """Stream JSONL with a hard per-record wire cap and bounded reads."""
    if (
        start_offset < 0
        or completed_lines < 0
        or max_line_bytes < 1
        or max_wire_record_bytes < max_line_bytes
    ):
        raise DataValidationError(
            "full_persona_record_limits_invalid",
            "Full-persona record limits or checkpoint are invalid.",
        )
    stream.seek(start_offset)
    line_number = completed_lines
    while True:
        byte_start = stream.tell()
        prefix = stream.readline(min(max_line_bytes + 1, max_wire_record_bytes + 1))
        if not prefix:
            return
        line_number += 1
        yield _finish_bounded_record(
            stream,
            prefix,
            byte_start=byte_start,
            line_number=line_number,
            max_line_bytes=max_line_bytes,
            max_wire_record_bytes=max_wire_record_bytes,
        )


def _finish_bounded_record(
    stream: BinaryIO,
    prefix: bytes,
    *,
    byte_start: int,
    line_number: int,
    max_line_bytes: int,
    max_wire_record_bytes: int,
) -> RawJsonlRecord:
    digest = hashlib.sha256(prefix)
    length = len(prefix)
    payload_parts = [prefix] if length <= max_line_bytes else []
    ended = prefix.endswith(b"\n")
    while not ended and length <= max_wire_record_bytes:
        remaining = max_wire_record_bytes - length
        chunk = stream.readline(min(max_line_bytes + 1, remaining + 1))
        if not chunk:
            break
        digest.update(chunk)
        length += len(chunk)
        if payload_parts and length <= max_line_bytes:
            payload_parts.append(chunk)
        else:
            payload_parts.clear()
        ended = chunk.endswith(b"\n")
    if length > max_wire_record_bytes:
        raise DataValidationError(
            "full_persona_wire_record_limit",
            "A JSONL record exceeded the hard full-persona wire limit.",
            details={"byte_start": byte_start, "consumed_bytes": length},
        )
    oversized = length > max_line_bytes
    return RawJsonlRecord(
        byte_start=byte_start,
        byte_length=length,
        line_number=line_number,
        record_sha256=digest.hexdigest(),
        payload=None if oversized else b"".join(payload_parts),
        oversized=oversized,
    )
