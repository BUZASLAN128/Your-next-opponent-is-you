from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from ynoy.corpus.types import authority_for_speaker, claim_holder_for_speaker
from ynoy.models import DataClass, ScopeRef, SourceEvent, Speaker
from ynoy.util import sha256_text

SourceKind = Literal["response_item_message", "event_message"]


@dataclass(frozen=True, slots=True)
class DraftMessage:
    sequence_index: int
    source_kind: SourceKind
    speaker: Speaker
    content: str
    timestamp: datetime | None
    turn_raw: str | None


def build_sample_events(
    drafts: Sequence[DraftMessage],
    *,
    namespace: str,
    thread_raw: str,
    parent_thread_raw: str | None,
    source_digest: str,
    import_run_id: UUID,
    source_data_class: DataClass,
) -> list[SourceEvent]:
    thread_key = _opaque(namespace, "thread", thread_raw)
    parent_key = (
        _opaque(namespace, "thread", parent_thread_raw) if parent_thread_raw is not None else None
    )
    return [
        _source_event(
            draft, thread_key, parent_key, source_digest, import_run_id, source_data_class
        )
        for draft in drafts
    ]


def record_time(record: Mapping[str, Any]) -> datetime | None:
    payload = record.get("payload")
    payload_map = payload if isinstance(payload, Mapping) else {}
    value = record.get("timestamp") or payload_map.get("timestamp")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _source_event(
    draft: DraftMessage,
    thread_key: str,
    parent_thread_key: str | None,
    source_digest: str,
    import_run_id: UUID,
    source_data_class: DataClass,
) -> SourceEvent:
    event_id = sha256_text(
        f"{source_digest}:record:{draft.sequence_index}:{draft.source_kind}:{draft.speaker.value}"
    )
    content_sha256 = sha256_text(draft.content)
    repeat_key = sha256_text(f"{thread_key}:{draft.speaker.value}:{content_sha256}")
    global_repeat_key = sha256_text(f"{draft.speaker.value}:{content_sha256}")
    turn_key = _opaque(thread_key, "turn", draft.turn_raw) if draft.turn_raw else None
    metadata = _event_metadata(draft, parent_thread_key, turn_key, repeat_key, global_repeat_key)
    created_at = draft.timestamp or datetime(1970, 1, 1, tzinfo=UTC)
    return SourceEvent(
        record_id=uuid5(NAMESPACE_URL, event_id),
        created_at=created_at,
        import_run_id=import_run_id,
        source_id=source_digest,
        source_locator=f"codex://{thread_key}/{event_id}",
        conversation_id=thread_key,
        branch_id=thread_key,
        event_id=event_id,
        parent_event_id=None,
        speaker=draft.speaker,
        claim_holder=claim_holder_for_speaker(draft.speaker),
        source_authority=authority_for_speaker(draft.speaker),
        data_class=source_data_class,
        event_time=draft.timestamp,
        content=draft.content,
        content_sha256=content_sha256,
        origin_cluster_id=thread_key,
        scope=ScopeRef(person_id="self"),
        metadata=metadata,
    )


def _event_metadata(
    draft: DraftMessage,
    parent_thread_key: str | None,
    turn_key: str | None,
    repeat_key: str,
    global_repeat_key: str,
) -> dict[str, object]:
    return {
        "source_kind": draft.source_kind,
        "sequence_index": draft.sequence_index,
        "thread_parent_key": parent_thread_key,
        "thread_lineage": "explicit_parent_thread" if parent_thread_key else "parent_unknown",
        "turn_key": turn_key,
        "repeat_cluster_key": repeat_key,
        "global_exact_content_key": global_repeat_key,
        "imported_instruction_is_inert": True,
        "claim_attribution_status": (
            "unreviewed_span" if draft.speaker == Speaker.USER else "speaker_context_only"
        ),
        "interpretation_authority": "none",
        "not_persisted": True,
        "core_eligible": False,
    }


def _opaque(namespace: str, kind: str, raw: str) -> str:
    return sha256_text(f"{namespace}:{kind}:{raw}")
