from __future__ import annotations

import io

import pytest

from ynoy.errors import DataValidationError
from ynoy.full_persona.records import iter_bounded_jsonl_records


class _BoundedStream(io.BytesIO):
    requests: list[int]

    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.requests = []

    def readline(self, size: int = -1) -> bytes:
        self.requests.append(size)
        return super().readline(size)


def test_reader_yields_offsets_and_payloads_without_reading_whole_stream() -> None:
    stream = _BoundedStream(b'{"n":1}\n{"n":2}\n')

    records = list(iter_bounded_jsonl_records(stream, max_line_bytes=32, max_wire_record_bytes=64))

    assert [record.payload for record in records] == [b'{"n":1}\n', b'{"n":2}\n']
    assert [record.byte_start for record in records] == [0, 8]
    assert [record.line_number for record in records] == [1, 2]
    assert stream.requests and max(stream.requests) <= 33


def test_newline_less_record_above_wire_cap_aborts_before_unbounded_read() -> None:
    stream = _BoundedStream(b"x" * 65)

    with pytest.raises(DataValidationError) as error:
        list(iter_bounded_jsonl_records(stream, max_line_bytes=8, max_wire_record_bytes=16))

    assert error.value.code == "full_persona_wire_record_limit"
    assert max(stream.requests) <= 17


def test_oversized_newline_terminated_record_is_quarantinable() -> None:
    record = b"x" * 17 + b"\n"

    records = list(
        iter_bounded_jsonl_records(io.BytesIO(record), max_line_bytes=16, max_wire_record_bytes=32)
    )

    assert len(records) == 1
    assert records[0].oversized is True
    assert records[0].payload is None
    assert records[0].byte_length == len(record)
