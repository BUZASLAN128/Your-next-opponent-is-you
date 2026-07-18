from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ynoy.models import Speaker

MessageSourceKind = Literal["response_item_message", "event_message"]
_ACTION_TYPES = frozenset(
    {
        "function_call",
        "function_call_output",
        "custom_tool_call",
        "custom_tool_call_output",
        "mcp_tool_call",
        "web_search_call",
    }
)


@dataclass(frozen=True, slots=True)
class MessageCandidate:
    speaker: Speaker
    content: str
    source_kind: MessageSourceKind


def message_candidate(outer_type: str, payload: Mapping[str, Any]) -> MessageCandidate | None:
    if outer_type == "response_item" and payload.get("type") == "message":
        role = str(payload.get("role", "unknown")).casefold()
        speaker = {
            "user": Speaker.USER,
            "assistant": Speaker.ASSISTANT,
            "system": Speaker.SYSTEM,
            "developer": Speaker.SYSTEM,
            "tool": Speaker.TOOL,
        }.get(role, Speaker.UNKNOWN)
        return MessageCandidate(
            speaker, _response_text(payload.get("content")), "response_item_message"
        )
    if outer_type == "event_msg":
        kind = str(payload.get("type", ""))
        event_speaker = {
            "user_message": Speaker.USER,
            "agent_message": Speaker.ASSISTANT,
        }.get(kind)
        content = payload.get("message") or payload.get("text")
        if event_speaker is not None and isinstance(content, str):
            return MessageCandidate(event_speaker, content.strip(), "event_message")
    return None


def safe_action_metadata(outer_type: str, payload: Mapping[str, Any]) -> dict[str, object]:
    payload_type = str(payload.get("type", ""))
    if outer_type != "response_item" or payload_type not in _ACTION_TYPES:
        return {}
    name = _bounded_label(payload.get("name") or payload.get("tool_name"), "unknown_tool")
    status = _action_status(payload_type, payload.get("status"))
    metadata: dict[str, object] = {"tool_name": name, "result_status": status}
    exit_code = payload.get("exit_code")
    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
        metadata["exit_code"] = exit_code
    error_class = _bounded_label(payload.get("error_class"), "")
    if error_class:
        metadata["error_class"] = error_class
    return metadata


def is_internal_reasoning(outer_type: str, payload_type: str | None) -> bool:
    return outer_type == "response_item" and payload_type in {"reasoning", "agent_reasoning"}


def is_subagent_envelope(content: str) -> bool:
    normalized = content.lstrip().casefold()
    return normalized.startswith(
        ("<subagent_notification", "<subagent_message", "<agent_notification")
    )


def _response_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    accepted: list[str] = []
    for part in value:
        if not isinstance(part, Mapping):
            continue
        part_type = part.get("type")
        text = part.get("text")
        if part_type in {"input_text", "output_text"} and isinstance(text, str):
            accepted.append(text)
    return "\n".join(accepted).strip()


def _action_status(payload_type: str, value: object) -> str:
    if isinstance(value, str) and value.casefold() in {"completed", "failed", "cancelled"}:
        return value.casefold()
    return "observed_result" if payload_type.endswith("_output") else "requested"


def _bounded_label(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = value.strip()
    if not normalized or len(normalized.encode("utf-8")) > 128:
        return fallback
    return normalized
