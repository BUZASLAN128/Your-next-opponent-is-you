from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, BinaryIO
from uuid import UUID

from ynoy.constants import (
    DEFAULT_CODEX_PILOT_MAX_CONTENT_BYTES,
    DEFAULT_CODEX_PILOT_MAX_EVENTS,
    DEFAULT_CODEX_PILOT_MAX_FILE_BYTES,
    DEFAULT_CODEX_PILOT_MAX_FILES,
    DEFAULT_CODEX_PILOT_MAX_LINE_BYTES,
    DEFAULT_CODEX_PILOT_MAX_RECORDS,
    DEFAULT_CODEX_PILOT_MAX_TOTAL_BYTES,
)
from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.corpus.codex_sample_events import (
    DraftMessage,
    SourceKind,
    build_sample_events,
    record_time,
)
from ynoy.errors import DataValidationError
from ynoy.models import DataClass, SourceEvent, Speaker

_ALLOWLISTED_RECORD_TYPES = frozenset(
    {"compacted", "event_msg", "response_item", "session_meta", "turn_context", "world_state"}
)
_ALLOWLISTED_PAYLOAD_TYPES = frozenset(
    {"agent_message", "agent_reasoning", "message", "token_count", "user_message"}
)


@dataclass(frozen=True, slots=True)
class CodexContentPilotLimits:
    max_files: int = DEFAULT_CODEX_PILOT_MAX_FILES
    max_total_input_bytes: int = DEFAULT_CODEX_PILOT_MAX_TOTAL_BYTES
    max_file_bytes: int = DEFAULT_CODEX_PILOT_MAX_FILE_BYTES
    max_line_bytes: int = DEFAULT_CODEX_PILOT_MAX_LINE_BYTES
    max_records: int = DEFAULT_CODEX_PILOT_MAX_RECORDS
    max_events: int = DEFAULT_CODEX_PILOT_MAX_EVENTS
    max_content_bytes: int = DEFAULT_CODEX_PILOT_MAX_CONTENT_BYTES

    def __post_init__(self) -> None:
        values = (
            self.max_files,
            self.max_total_input_bytes,
            self.max_file_bytes,
            self.max_line_bytes,
            self.max_records,
            self.max_events,
            self.max_content_bytes,
        )
        if any(value < 1 for value in values):
            raise DataValidationError(
                "codex_pilot_invalid_limit", "Codex content pilot limits must be positive."
            )
        if self.max_file_bytes > self.max_total_input_bytes:
            raise DataValidationError(
                "codex_pilot_invalid_limit",
                "The per-file pilot limit cannot exceed the total input limit.",
            )


@dataclass(frozen=True, slots=True)
class ParsedCodexSampleFile:
    events: tuple[SourceEvent, ...]
    source_digest: str
    record_count: int
    record_type_counts: dict[str, int]
    excluded_counts: dict[str, int]
    explicit_parent_thread: bool


@dataclass(slots=True)
class _ReadState:
    drafts: list[DraftMessage] = field(default_factory=list)
    record_types: Counter[str] = field(default_factory=Counter)
    excluded: Counter[str] = field(default_factory=Counter)
    thread_raw: str | None = None
    parent_thread_raw: str | None = None
    current_turn_raw: str | None = None
    record_count: int = 0


def parse_codex_sample_file(
    item: DiscoveredCodexFile,
    *,
    namespace: str,
    import_run_id: UUID,
    source_data_class: DataClass,
    limits: CodexContentPilotLimits,
    remaining_records: int,
    remaining_events: int,
) -> ParsedCodexSampleFile:
    """Parse allowlisted dialogue records from one stable, bounded rollout file."""

    state = _ReadState()
    with open_stable_codex_file(item) as stream:
        source_digest = _consume_lines(stream, state, limits, remaining_records, remaining_events)
    if state.thread_raw is None:
        state.thread_raw = f"missing:{item.partition}:{item.relative.as_posix()}"
        state.excluded["missing_thread_id"] += 1
    events = build_sample_events(
        state.drafts,
        namespace=namespace,
        thread_raw=state.thread_raw,
        parent_thread_raw=state.parent_thread_raw,
        source_digest=source_digest,
        import_run_id=import_run_id,
        source_data_class=source_data_class,
    )
    return ParsedCodexSampleFile(
        tuple(events),
        source_digest,
        state.record_count,
        dict(sorted(state.record_types.items())),
        dict(sorted(state.excluded.items())),
        state.parent_thread_raw is not None,
    )


def _consume_lines(
    stream: BinaryIO,
    state: _ReadState,
    limits: CodexContentPilotLimits,
    remaining_records: int,
    remaining_events: int,
) -> str:
    digest = hashlib.sha256()
    while True:
        line = stream.readline(limits.max_line_bytes + 1)
        if not line:
            break
        if len(line) > limits.max_line_bytes:
            raise DataValidationError(
                "codex_pilot_line_limit", "A Codex pilot record exceeds the line-size limit."
            )
        state.record_count += 1
        if state.record_count > remaining_records:
            raise DataValidationError(
                "codex_pilot_record_limit", "The Codex pilot exceeds its record limit."
            )
        digest.update(line)
        record = _decode_record(line)
        _handle_record(record, state, limits)
        if len(state.drafts) > remaining_events:
            raise DataValidationError(
                "codex_pilot_event_limit", "The Codex pilot exceeds its dialogue-event limit."
            )
    if state.record_count == 0:
        raise DataValidationError("codex_pilot_empty_file", "A selected Codex rollout is empty.")
    return digest.hexdigest()


def _decode_record(line: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "codex_pilot_invalid_jsonl", "A selected Codex rollout contains invalid JSONL."
        ) from exc
    if not isinstance(value, Mapping):
        raise DataValidationError(
            "codex_pilot_invalid_record", "Every selected Codex record must be a JSON object."
        )
    return value


def _handle_record(
    record: Mapping[str, Any], state: _ReadState, limits: CodexContentPilotLimits
) -> None:
    outer_type = str(record.get("type", "unknown"))
    state.record_types[_allowlisted_category(outer_type, _ALLOWLISTED_RECORD_TYPES)] += 1
    payload = record.get("payload")
    payload_map = payload if isinstance(payload, Mapping) else {}
    if state.record_count == 1:
        _capture_session_meta(outer_type, payload_map, state)
        return
    if outer_type == "turn_context":
        state.current_turn_raw = _optional_text(payload_map.get("turn_id"))
        state.excluded["turn_context"] += 1
        return
    draft = _response_message(record, payload_map, state, limits)
    if draft is None:
        draft = _event_message(record, payload_map, state, limits)
    if draft is None:
        state.excluded[_excluded_kind(outer_type, payload_map)] += 1
        return
    state.drafts.append(draft)


def _capture_session_meta(outer_type: str, payload: Mapping[str, Any], state: _ReadState) -> None:
    if outer_type != "session_meta":
        raise DataValidationError(
            "codex_pilot_session_meta_required",
            "A selected Codex rollout must begin with session metadata.",
        )
    state.thread_raw = _optional_text(payload.get("id") or payload.get("session_id"))
    state.parent_thread_raw = _optional_text(payload.get("parent_thread_id"))
    state.excluded["session_meta"] += 1


def _response_message(
    record: Mapping[str, Any],
    payload: Mapping[str, Any],
    state: _ReadState,
    limits: CodexContentPilotLimits,
) -> DraftMessage | None:
    if record.get("type") != "response_item" or payload.get("type") != "message":
        return None
    role = str(payload.get("role", "unknown")).casefold()
    speaker = {"user": Speaker.USER, "assistant": Speaker.ASSISTANT}.get(role)
    if speaker is None:
        state.excluded["control_message"] += 1
        return None
    content = _response_text(payload.get("content"), state)
    return _draft(record, content, speaker, "response_item_message", state, limits)


def _event_message(
    record: Mapping[str, Any],
    payload: Mapping[str, Any],
    state: _ReadState,
    limits: CodexContentPilotLimits,
) -> DraftMessage | None:
    if record.get("type") != "event_msg":
        return None
    kind = str(payload.get("type", ""))
    speaker = {"user_message": Speaker.USER, "agent_message": Speaker.ASSISTANT}.get(kind)
    if speaker is None:
        return None
    content = payload.get("message") or payload.get("text")
    text = content.strip() if isinstance(content, str) else ""
    return _draft(record, text, speaker, "event_message", state, limits)


def _draft(
    record: Mapping[str, Any],
    content: str,
    speaker: Speaker,
    source_kind: SourceKind,
    state: _ReadState,
    limits: CodexContentPilotLimits,
) -> DraftMessage | None:
    if not content:
        state.excluded["empty_dialogue_message"] += 1
        return None
    if len(content.encode("utf-8")) > limits.max_content_bytes:
        raise DataValidationError(
            "codex_pilot_content_limit", "A Codex pilot message exceeds the content limit."
        )
    payload = record.get("payload")
    payload_map = payload if isinstance(payload, Mapping) else {}
    turn_raw = _optional_text(payload_map.get("turn_id")) or state.current_turn_raw
    return DraftMessage(
        state.record_count, source_kind, speaker, content, record_time(record), turn_raw
    )


def _response_text(value: object, state: _ReadState) -> str:
    if not isinstance(value, list):
        state.excluded["unsupported_content_container"] += 1
        return ""
    accepted: list[str] = []
    for part in value:
        if not isinstance(part, Mapping):
            state.excluded["non_object_content_part"] += 1
            continue
        part_type = str(part.get("type", "unknown"))
        text = part.get("text")
        if part_type in {"input_text", "output_text"} and isinstance(text, str):
            accepted.append(text)
        else:
            category = "non_text" if part_type == "input_image" else "other"
            state.excluded[f"content_part:{category}"] += 1
    return "\n".join(accepted).strip()


def _excluded_kind(outer_type: str, payload: Mapping[str, Any]) -> str:
    outer = _allowlisted_category(outer_type, _ALLOWLISTED_RECORD_TYPES)
    inner = payload.get("type")
    if not isinstance(inner, str):
        return f"record:{outer}"
    return f"record:{outer}:{_allowlisted_category(inner, _ALLOWLISTED_PAYLOAD_TYPES)}"


def _allowlisted_category(value: str, allowed: frozenset[str]) -> str:
    return value if value in allowed else "other"


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
