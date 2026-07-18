from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.constants import CODEX_INGEST_VERSION
from ynoy.models.base import (
    ClaimHolder,
    DataClass,
    RecordBase,
    SourceAuthority,
    Speaker,
)
from ynoy.util import canonical_sha256


class CodexActorOrigin(StrEnum):
    USER_CANDIDATE = "user_candidate"
    ASSISTANT = "assistant"
    SUBAGENT_DELEGATION = "subagent_delegation"
    SYSTEM_CONTROL = "system_control"
    TOOL = "tool"
    UNKNOWN = "unknown"


class NormalizedCodexEvent(RecordBase):
    snapshot_id: UUID
    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    blob_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_start: int = Field(ge=0)
    byte_length: int = Field(ge=1)
    line_number: int = Field(ge=1)
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_type: str = Field(min_length=1)
    payload_type: str | None = None
    actor_origin: CodexActorOrigin
    structural_role: Speaker
    claim_holder: ClaimHolder
    source_authority: SourceAuthority
    status: Literal["dialogue", "safe_action", "quarantined"]
    content: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_time: datetime | None = None
    conversation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    turn_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    duplicate_of: UUID | None = None
    exclusion_reason: str | None = None
    safe_action_metadata: dict[str, Any] = Field(default_factory=dict)
    data_class: DataClass
    synthetic: bool
    parser_version: Literal["codex-normalized-dialogue/1.0"] = CODEX_INGEST_VERSION
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def normalized_event_is_consistent(self) -> NormalizedCodexEvent:
        _validate_event_plane(self)
        _validate_event_payload(self)
        _validate_user_origin(self)
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"event_sha256"}))
        if self.event_sha256 != expected:
            raise ValueError("normalized event hash does not match its payload")
        return self


class CodexIngestionReceipt(RecordBase):
    snapshot_id: UUID
    snapshot_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_data_class: DataClass
    synthetic: bool
    normalized_event_count: int = Field(ge=0)
    dialogue_event_count: int = Field(ge=0)
    safe_action_event_count: int = Field(ge=0)
    quarantined_event_count: int = Field(ge=0)
    processed_file_count: int = Field(ge=0)
    processed_bytes: int = Field(ge=0)
    status: Literal["complete", "partial"]
    parser_version: Literal["codex-normalized-dialogue/1.0"] = CODEX_INGEST_VERSION
    model_provider_used: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def ingestion_receipt_is_consistent(self) -> CodexIngestionReceipt:
        expected_class = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.source_data_class != expected_class:
            raise ValueError("ingestion receipt data class contradicts its mode")
        total = (
            self.dialogue_event_count + self.safe_action_event_count + self.quarantined_event_count
        )
        if total != self.normalized_event_count:
            raise ValueError("ingestion event counts do not reconcile")
        if self.receipt_sha256 != canonical_sha256(
            self.model_dump(mode="json", exclude={"receipt_sha256"})
        ):
            raise ValueError("ingestion receipt hash does not match its payload")
        return self


def _validate_event_plane(event: NormalizedCodexEvent) -> None:
    expected = DataClass.PUBLIC_SYNTHETIC if event.synthetic else DataClass.RAW_CORPUS
    if event.data_class != expected:
        raise ValueError("normalized event data class contradicts its mode")


def _validate_event_payload(event: NormalizedCodexEvent) -> None:
    dialogue = event.status == "dialogue"
    safe_action = event.status == "safe_action"
    if dialogue != (event.content is not None and event.content_sha256 is not None):
        raise ValueError("dialogue alone may retain normalized content")
    if safe_action != bool(event.safe_action_metadata):
        raise ValueError("safe action metadata belongs only to action events")
    if (event.status == "quarantined") != (event.exclusion_reason is not None):
        raise ValueError("quarantined events require one exclusion reason")
    if event.duplicate_of is not None and event.exclusion_reason != "duplicate_representation":
        raise ValueError("duplicate binding requires duplicate quarantine")


def _validate_user_origin(event: NormalizedCodexEvent) -> None:
    if event.actor_origin == CodexActorOrigin.USER_CANDIDATE:
        valid = (
            event.structural_role == Speaker.USER
            and event.claim_holder == ClaimHolder.UNKNOWN
            and event.source_authority == SourceAuthority.USER_TURN_UNATTRIBUTED
            and (
                event.status == "dialogue"
                or (
                    event.status == "quarantined"
                    and event.exclusion_reason == "duplicate_representation"
                )
            )
        )
        if not valid:
            raise ValueError("user candidate attribution is inconsistent")
    if event.actor_origin == CodexActorOrigin.SUBAGENT_DELEGATION and event.status == "dialogue":
        raise ValueError("subagent or delegation content cannot enter active dialogue")
