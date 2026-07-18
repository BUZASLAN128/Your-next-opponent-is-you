from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from ynoy.constants import CODEX_INGEST_MAX_CONTENT_BYTES
from ynoy.corpus.codex_normalizer_content import (
    MessageCandidate,
    is_internal_reasoning,
    is_subagent_envelope,
    message_candidate,
    safe_action_metadata,
)
from ynoy.corpus.codex_normalizer_types import (
    CodexFileBinding,
    CodexParserState,
    RecordClassification,
    quarantine,
    seal_normalized_event,
)
from ynoy.corpus.codex_raw_records import RawJsonlRecord
from ynoy.models import (
    CodexActorOrigin,
    NormalizedCodexEvent,
    Speaker,
)
from ynoy.util import sha256_text

_OUTER_TYPES = frozenset(
    {"session_meta", "turn_context", "response_item", "event_msg", "compacted", "world_state"}
)
_PAYLOAD_TYPES = frozenset(
    {
        "message",
        "user_message",
        "agent_message",
        "reasoning",
        "agent_reasoning",
        "function_call",
        "function_call_output",
        "custom_tool_call",
        "custom_tool_call_output",
        "mcp_tool_call",
        "web_search_call",
    }
)


def normalize_codex_record(
    raw: RawJsonlRecord,
    state: CodexParserState,
    binding: CodexFileBinding,
) -> NormalizedCodexEvent:
    record, decode_error = _decode(raw)
    outer_type, payload_type, payload = _record_shape(record)
    classification = _classify(
        raw, state, binding, record, payload, outer_type, payload_type, decode_error
    )
    record_id = uuid5(
        NAMESPACE_URL,
        f"{binding.snapshot_id}:{binding.source_key}:{raw.byte_start}:{raw.record_sha256}",
    )
    classification = _deduplicate(classification, state, record_id, raw.line_number)
    return seal_normalized_event(
        raw, binding, state, record_id, outer_type, payload_type, record, classification
    )


def _decode(raw: RawJsonlRecord) -> tuple[Mapping[str, Any] | None, str | None]:
    if raw.oversized or raw.payload is None:
        return None, "oversized_record"
    try:
        value = json.loads(raw.payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(value, Mapping):
        return None, "non_object_record"
    return value, None


def _record_shape(
    record: Mapping[str, Any] | None,
) -> tuple[str, str | None, Mapping[str, Any]]:
    if record is None:
        return "other", None, {}
    outer_raw = record.get("type")
    outer = outer_raw if isinstance(outer_raw, str) and outer_raw in _OUTER_TYPES else "other"
    payload_raw = record.get("payload")
    payload = payload_raw if isinstance(payload_raw, Mapping) else {}
    inner_raw = payload.get("type")
    inner = inner_raw if isinstance(inner_raw, str) and inner_raw in _PAYLOAD_TYPES else None
    return outer, inner, payload


def _classify(
    raw: RawJsonlRecord,
    state: CodexParserState,
    binding: CodexFileBinding,
    record: Mapping[str, Any] | None,
    payload: Mapping[str, Any],
    outer: str,
    inner: str | None,
    decode_error: str | None,
) -> RecordClassification:
    if decode_error:
        return quarantine(CodexActorOrigin.UNKNOWN, Speaker.UNKNOWN, decode_error)
    if outer == "session_meta":
        _capture_session(state, binding, payload)
        return quarantine(CodexActorOrigin.SYSTEM_CONTROL, Speaker.SYSTEM, "session_metadata")
    if outer == "turn_context":
        _capture_turn(state, binding, payload)
        return quarantine(CodexActorOrigin.SYSTEM_CONTROL, Speaker.SYSTEM, "turn_context")
    candidate = message_candidate(outer, payload)
    if candidate is not None:
        return _classify_message(candidate, state)
    action = safe_action_metadata(outer, payload)
    if action:
        return RecordClassification(
            CodexActorOrigin.TOOL, Speaker.TOOL, "safe_action", action=action
        )
    if is_internal_reasoning(outer, inner):
        return quarantine(CodexActorOrigin.ASSISTANT, Speaker.ASSISTANT, "internal_reasoning")
    del raw, record
    return quarantine(CodexActorOrigin.UNKNOWN, Speaker.UNKNOWN, "unsupported_record")


def _classify_message(message: MessageCandidate, state: CodexParserState) -> RecordClassification:
    if not state.session_meta_seen:
        return quarantine(CodexActorOrigin.UNKNOWN, message.speaker, "session_origin_unverified")
    if message.speaker == Speaker.USER:
        delegated = state.delegated_session or is_subagent_envelope(message.content)
        if delegated:
            return quarantine(
                CodexActorOrigin.SUBAGENT_DELEGATION,
                Speaker.USER,
                "subagent_or_delegation",
            )
        return _dialogue(CodexActorOrigin.USER_CANDIDATE, message)
    if message.speaker == Speaker.ASSISTANT:
        return _dialogue(CodexActorOrigin.ASSISTANT, message)
    origin = (
        CodexActorOrigin.TOOL
        if message.speaker == Speaker.TOOL
        else CodexActorOrigin.SYSTEM_CONTROL
    )
    return quarantine(origin, message.speaker, "control_or_tool_content")


def _dialogue(origin: CodexActorOrigin, message: MessageCandidate) -> RecordClassification:
    if not message.content:
        return quarantine(origin, message.speaker, "empty_dialogue")
    if len(message.content.encode("utf-8")) > CODEX_INGEST_MAX_CONTENT_BYTES:
        return quarantine(origin, message.speaker, "oversized_content")
    return RecordClassification(
        origin,
        message.speaker,
        "dialogue",
        content=message.content,
        source_kind=message.source_kind,
    )


def _deduplicate(
    item: RecordClassification,
    state: CodexParserState,
    record_id: UUID,
    line_number: int,
) -> RecordClassification:
    if item.status != "dialogue" or item.content is None or item.source_kind is None:
        return item
    key = sha256_text(
        f"{state.conversation_key}:{state.turn_key}:{item.speaker.value}:{sha256_text(item.content)}"
    )
    previous = state.seen_dialogue.get(key)
    state.seen_dialogue[key] = f"{item.source_kind}:{record_id}:{line_number}"
    if len(state.seen_dialogue) > 2048:
        state.seen_dialogue = {key: state.seen_dialogue[key]}
    if previous is None:
        return item
    kind, raw_id, raw_line = previous.rsplit(":", 2)
    if kind == item.source_kind or line_number - int(raw_line) > 3:
        return item
    return replace(
        item,
        status="quarantined",
        content=None,
        exclusion="duplicate_representation",
        duplicate_of=UUID(raw_id),
    )


def _capture_session(
    state: CodexParserState, binding: CodexFileBinding, payload: Mapping[str, Any]
) -> None:
    raw_id = payload.get("id") or payload.get("session_id")
    state.session_meta_seen = True
    state.conversation_key = sha256_text(
        f"{binding.snapshot_id}:{binding.source_key}:conversation:{raw_id or 'missing'}"
    )
    source = str(payload.get("source", "")).casefold()
    originator = str(payload.get("originator", "")).casefold()
    state.delegated_session = bool(payload.get("parent_thread_id")) or any(
        "subagent" in value or "delegate" in value for value in (source, originator)
    )


def _capture_turn(
    state: CodexParserState, binding: CodexFileBinding, payload: Mapping[str, Any]
) -> None:
    raw_turn = payload.get("turn_id")
    state.turn_key = (
        sha256_text(f"{binding.snapshot_id}:{binding.source_key}:turn:{raw_turn}")
        if isinstance(raw_turn, str) and raw_turn
        else None
    )
    state.seen_dialogue.clear()
