from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from ynoy.corpus.codex_raw_records import RawJsonlRecord
from ynoy.corpus.codex_sample_events import record_time
from ynoy.models import (
    ClaimHolder,
    CodexActorOrigin,
    DataClass,
    NormalizedCodexEvent,
    SourceAuthority,
    Speaker,
)
from ynoy.util import canonical_sha256, sha256_text


@dataclass(frozen=True, slots=True)
class CodexFileBinding:
    snapshot_id: UUID
    source_key: str
    blob_sha256: str
    data_class: DataClass
    synthetic: bool


@dataclass(slots=True)
class CodexParserState:
    session_meta_seen: bool = False
    conversation_key: str | None = None
    delegated_session: bool = False
    turn_key: str | None = None
    seen_dialogue: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        return {
            "session_meta_seen": self.session_meta_seen,
            "conversation_key": self.conversation_key,
            "delegated_session": self.delegated_session,
            "turn_key": self.turn_key,
            "seen_dialogue": dict(sorted(self.seen_dialogue.items())),
        }

    @classmethod
    def from_payload(cls, value: object) -> CodexParserState:
        if not isinstance(value, Mapping):
            return cls()
        seen = value.get("seen_dialogue")
        safe_seen = (
            {str(key): str(item) for key, item in seen.items()}
            if isinstance(seen, Mapping) and len(seen) <= 2048
            else {}
        )
        return cls(
            session_meta_seen=value.get("session_meta_seen") is True,
            conversation_key=_digest_or_none(value.get("conversation_key")),
            delegated_session=value.get("delegated_session") is True,
            turn_key=_digest_or_none(value.get("turn_key")),
            seen_dialogue=safe_seen,
        )


@dataclass(frozen=True, slots=True)
class RecordClassification:
    origin: CodexActorOrigin
    speaker: Speaker
    status: Literal["dialogue", "safe_action", "quarantined"]
    content: str | None = None
    exclusion: str | None = None
    action: dict[str, object] = field(default_factory=dict)
    source_kind: str | None = None
    duplicate_of: UUID | None = None


def quarantine(origin: CodexActorOrigin, speaker: Speaker, reason: str) -> RecordClassification:
    return RecordClassification(origin, speaker, "quarantined", exclusion=reason)


def seal_normalized_event(
    raw: RawJsonlRecord,
    binding: CodexFileBinding,
    state: CodexParserState,
    record_id: UUID,
    outer: str,
    inner: str | None,
    record: Mapping[str, object] | None,
    item: RecordClassification,
) -> NormalizedCodexEvent:
    holder, authority = _attribution(item.origin)
    timestamp = record_time(record or {})
    content_hash = sha256_text(item.content) if item.content is not None else None
    draft = NormalizedCodexEvent.model_construct(
        record_id=record_id,
        created_at=timestamp or datetime(1970, 1, 1, tzinfo=UTC),
        snapshot_id=binding.snapshot_id,
        source_key=binding.source_key,
        blob_sha256=binding.blob_sha256,
        byte_start=raw.byte_start,
        byte_length=raw.byte_length,
        line_number=raw.line_number,
        record_sha256=raw.record_sha256,
        record_type=outer,
        payload_type=inner,
        actor_origin=item.origin,
        structural_role=item.speaker,
        claim_holder=holder,
        source_authority=authority,
        status=item.status,
        content=item.content,
        content_sha256=content_hash,
        event_time=timestamp,
        conversation_key=state.conversation_key,
        turn_key=state.turn_key,
        duplicate_of=item.duplicate_of,
        exclusion_reason=item.exclusion,
        safe_action_metadata=item.action,
        data_class=binding.data_class,
        synthetic=binding.synthetic,
        event_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"event_sha256"})
    return NormalizedCodexEvent.model_validate(
        {**draft.model_dump(mode="python"), "event_sha256": canonical_sha256(payload)}
    )


def _attribution(origin: CodexActorOrigin) -> tuple[ClaimHolder, SourceAuthority]:
    if origin == CodexActorOrigin.USER_CANDIDATE:
        return ClaimHolder.UNKNOWN, SourceAuthority.USER_TURN_UNATTRIBUTED
    if origin == CodexActorOrigin.ASSISTANT:
        return ClaimHolder.ASSISTANT, SourceAuthority.ASSISTANT_CONTEXT
    if origin in {
        CodexActorOrigin.SUBAGENT_DELEGATION,
        CodexActorOrigin.SYSTEM_CONTROL,
        CodexActorOrigin.TOOL,
    }:
        return ClaimHolder.UNKNOWN, SourceAuthority.SYSTEM_CONTROL
    return ClaimHolder.UNKNOWN, SourceAuthority.UNKNOWN


def _digest_or_none(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 64:
        return None
    return value if all(char in "0123456789abcdef" for char in value) else None
