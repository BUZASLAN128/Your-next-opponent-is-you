from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.constants import POLICY_VERSION
from ynoy.models.base import (
    ClaimHolder,
    DataClass,
    RecordBase,
    ScopeRef,
    SourceAuthority,
    Speaker,
    StrictModel,
)


class SourceEvent(RecordBase):
    import_run_id: UUID
    source_id: str
    source_locator: str
    conversation_id: str
    branch_id: str
    event_id: str
    parent_event_id: str | None = None
    speaker: Speaker
    quoted_speaker: Speaker | None = None
    claim_holder: ClaimHolder = ClaimHolder.UNKNOWN
    source_authority: SourceAuthority
    data_class: DataClass
    event_time: datetime | None = None
    content: str
    content_sha256: str
    origin_cluster_id: str
    scope: ScopeRef = Field(default_factory=ScopeRef)
    revision_of: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def speaker_authority_agree(self) -> SourceEvent:
        explicit_user = self.source_authority == SourceAuthority.EXPLICIT_USER_STATEMENT
        if explicit_user and self.speaker != Speaker.USER:
            raise ValueError("only user-authored events may be explicit user statements")
        unattributed_user = self.source_authority == SourceAuthority.USER_TURN_UNATTRIBUTED
        if unattributed_user and self.speaker != Speaker.USER:
            raise ValueError("only user turns may use unattributed user-turn authority")
        laundered_user = (
            self.speaker == Speaker.ASSISTANT and self.claim_holder == ClaimHolder.REPRESENTED_USER
        )
        if laundered_user:
            raise ValueError("assistant text cannot directly become represented-user evidence")
        if unattributed_user and self.claim_holder == ClaimHolder.REPRESENTED_USER:
            raise ValueError("unreviewed user turns cannot claim represented-user adoption")
        return self


class SourceReceipt(RecordBase):
    import_run_id: UUID
    source_id: str
    adapter: str
    parser_version: str
    source_archive_sha256: str
    normalized_event_count: int = Field(ge=0)
    excluded_event_count: int = Field(ge=0)
    speaker_counts: dict[str, int] = Field(default_factory=dict)
    status: Literal["complete", "partial", "rejected"]
    warnings: tuple[str, ...] = ()


class InventoryEntry(StrictModel):
    name: str
    compressed_bytes: int = Field(ge=0)
    uncompressed_bytes: int = Field(ge=0)
    compression_ratio: float = Field(ge=0.0)
    selected_for_parser: bool = False


class InventoryManifest(RecordBase):
    adapter: Literal["chatgpt_zip"] = "chatgpt_zip"
    parser_version: str
    policy_version: str = POLICY_VERSION
    source_name: str
    source_archive_sha256: str
    source_bytes: int = Field(ge=0)
    entries: tuple[InventoryEntry, ...]
    entry_count: int = Field(ge=0)
    total_uncompressed_bytes: int = Field(ge=0)
    conversation_count: int = Field(ge=0)
    message_count: int = Field(ge=0)
    branch_count: int = Field(ge=0)
    speaker_counts: dict[str, int]
    malformed_record_count: int = Field(ge=0)
    excluded_content_part_count: int = Field(ge=0)
    warnings: tuple[str, ...] = ()
    source_data_class: DataClass
    synthetic: bool
    manifest_sha256: str = ""

    @model_validator(mode="after")
    def classification_is_honest(self) -> InventoryManifest:
        if self.synthetic and self.source_data_class != DataClass.PUBLIC_SYNTHETIC:
            raise ValueError("synthetic inventory must use D0")
        if not self.synthetic and self.source_data_class == DataClass.PUBLIC_SYNTHETIC:
            raise ValueError("real inventory cannot use D0")
        return self


class IngestionApproval(RecordBase):
    manifest_id: UUID
    manifest_sha256: str
    purpose: Literal["scientific_personality_core"] = "scientific_personality_core"
    allowed_operations: tuple[Literal["ingest", "derive", "benchmark", "report"], ...]
    retention_days: int | None = Field(default=None, ge=1)
    third_party_reviewed: bool
    approved_by: Literal["represented_user"] = "represented_user"
    approval_sha256: str = ""
