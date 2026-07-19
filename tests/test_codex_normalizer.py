# ruff: noqa: RUF001 -- Turkish synthetic dialogue mirrors user input.

from __future__ import annotations

import io
import json
from collections.abc import Iterable
from uuid import UUID

import pytest

from ynoy.constants import CODEX_INGEST_MAX_CONTENT_BYTES
from ynoy.corpus.codex_normalizer import normalize_codex_record
from ynoy.corpus.codex_normalizer_types import CodexFileBinding, CodexParserState
from ynoy.corpus.codex_raw_records import iter_jsonl_records
from ynoy.full_persona.evidence import evidence_from_event
from ynoy.models import CodexActorOrigin, DataClass, Speaker
from ynoy.models.full_persona import FullCorpusLimits, FullCorpusSource
from ynoy.util import canonical_sha256


def _binding() -> CodexFileBinding:
    return CodexFileBinding(
        snapshot_id=UUID(int=1),
        source_key="1" * 64,
        blob_sha256="2" * 64,
        data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _evidence_source() -> FullCorpusSource:
    payload = {
        "partition": "sessions",
        "relative_locator": "fixture.jsonl",
        "source_key": "1" * 64,
        "file_bytes": 1,
        "modified_ns": 1,
        "device": 0,
        "inode": 0,
        "session_start_ns": 1,
        "thread_receipt": "2" * 64,
        "parent_thread_receipt": None,
        "lineage_component_receipt": "3" * 64,
        "blob_sha256": "4" * 64,
        "chunk_size_bytes": 64 * 1024,
        "chunk_sha256": ("5" * 64,),
    }
    return FullCorpusSource.model_validate({**payload, "source_receipt": canonical_sha256(payload)})


def _encode(records: Iterable[object]) -> bytes:
    return b"".join(json.dumps(record).encode() + b"\n" for record in records)


def _normalize(data: bytes, *, max_line_bytes: int = 16 * 1024 * 1024):
    state = CodexParserState()
    events = [
        normalize_codex_record(raw, state, _binding())
        for raw in iter_jsonl_records(io.BytesIO(data), max_line_bytes=max_line_bytes)
    ]
    return events, state


def _session(*, parent: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"id": "synthetic-session"}
    if parent is not None:
        payload["parent_thread_id"] = parent
    return {"type": "session_meta", "payload": payload}


def _message(role: str, text: str) -> dict[str, object]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": text}],
        },
    }


def test_user_and_assistant_dialogue_remain_separate_unattributed_planes() -> None:
    events, _ = _normalize(_encode((_session(), _message("user", "u"), _message("assistant", "a"))))

    user, assistant = events[1:]
    assert user.actor_origin == CodexActorOrigin.USER_CANDIDATE
    assert user.structural_role == Speaker.USER
    assert user.content == "u"
    assert user.source_authority.value == "user_turn_unattributed"
    assert assistant.actor_origin == CodexActorOrigin.ASSISTANT
    assert assistant.content == "a"
    assert assistant.source_authority.value == "assistant_context"


@pytest.mark.parametrize(
    ("text", "reason"),
    (
        ("", "empty_dialogue"),
        ("x" * (CODEX_INGEST_MAX_CONTENT_BYTES + 1), "oversized_content"),
    ),
    ids=["empty-content", "oversized-content"],
)
def test_structural_user_content_limits_quarantine_without_user_attribution(
    text: str, reason: str
) -> None:
    events, _ = _normalize(_encode((_session(), _message("user", text))))

    event = events[1]
    assert event.status == "quarantined"
    assert event.exclusion_reason == reason
    assert event.structural_role == Speaker.USER
    assert event.content is None
    assert event.actor_origin != CodexActorOrigin.USER_CANDIDATE
    assert event.source_authority.value != "user_turn_unattributed"
    evidence, exclusion = evidence_from_event(event, _evidence_source(), (), FullCorpusLimits())
    assert evidence is None
    assert exclusion == reason


def test_child_session_and_subagent_envelope_are_never_user_evidence() -> None:
    child, _ = _normalize(_encode((_session(parent="parent"), _message("user", "delegated"))))
    envelope, _ = _normalize(
        _encode(
            (_session(), _message("user", "<subagent_notification>result</subagent_notification>"))
        )
    )

    for event in (child[1], envelope[1]):
        assert event.status == "quarantined"
        assert event.content is None
        assert event.actor_origin == CodexActorOrigin.SUBAGENT_DELEGATION
        assert event.exclusion_reason == "subagent_or_delegation"


def test_delegated_session_origin_stays_sticky_across_rootlike_session_meta() -> None:
    records = (
        {
            "type": "session_meta",
            "payload": {
                "id": "synthetic-spawned-thread",
                "source": "subagent",
                "originator": "thread_spawn",
            },
        },
        {
            "type": "session_meta",
            "payload": {"id": "synthetic-rootlike-thread", "source": "vscode"},
        },
        _message("user", "Onaylıyorum, bunu uygula."),
    )

    events, state = _normalize(_encode(records))

    assert state.delegated_session is True
    assert events[2].status == "quarantined"
    assert events[2].actor_origin == CodexActorOrigin.SUBAGENT_DELEGATION
    assert events[2].exclusion_reason == "subagent_or_delegation"


def test_control_reasoning_and_tool_output_content_never_enter_dialogue() -> None:
    records = (
        _session(),
        _message("system", "hidden control"),
        {
            "type": "response_item",
            "payload": {"type": "reasoning", "summary": "hidden reasoning"},
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "name": "synthetic_tool",
                "status": "failed",
                "exit_code": 7,
                "error_class": "SyntheticError",
                "output": "raw secret output",
            },
        },
    )
    events, _ = _normalize(_encode(records))

    assert events[1].status == events[2].status == "quarantined"
    action = events[3]
    assert action.status == "safe_action"
    assert action.content is None
    assert action.safe_action_metadata == {
        "tool_name": "synthetic_tool",
        "result_status": "failed",
        "exit_code": 7,
        "error_class": "SyntheticError",
    }
    assert "raw secret output" not in action.model_dump_json()


def test_duplicate_response_and_event_representations_are_quarantined() -> None:
    records = (
        _session(),
        {"type": "turn_context", "payload": {"turn_id": "turn-1"}},
        _message("user", "same dialogue"),
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "same dialogue"},
        },
    )
    events, _ = _normalize(_encode(records))

    assert events[2].status == "dialogue"
    assert events[3].status == "quarantined"
    assert events[3].duplicate_of == events[2].record_id
    assert events[3].exclusion_reason == "duplicate_representation"


def test_invalid_unknown_and_oversized_records_keep_exact_byte_accounting() -> None:
    data = b"not-json\n" + _encode(({"type": "new_future_type", "payload": {}},)) + b"x" * 80
    events, _ = _normalize(data, max_line_bytes=64)

    assert [event.exclusion_reason for event in events] == [
        "invalid_json",
        "unsupported_record",
        "oversized_record",
    ]
    assert sum(event.byte_length for event in events) == len(data)
    assert events[-1].byte_start + events[-1].byte_length == len(data)


def test_serialized_parser_state_resumes_to_identical_event_stream() -> None:
    data = _encode((_session(), _message("user", "one"), _message("assistant", "two")))
    full, _ = _normalize(data)
    raw = list(iter_jsonl_records(io.BytesIO(data)))
    state = CodexParserState()
    first = normalize_codex_record(raw[0], state, _binding())
    resumed = CodexParserState.from_payload(state.to_payload())
    remaining = [normalize_codex_record(item, resumed, _binding()) for item in raw[1:]]

    assert [event.event_sha256 for event in [first, *remaining]] == [
        event.event_sha256 for event in full
    ]
