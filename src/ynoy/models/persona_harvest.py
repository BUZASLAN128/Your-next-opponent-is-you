from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ynoy.constants import (
    CODEX_HARVEST_MAX_ARTIFACT_BYTES,
    CODEX_HARVEST_MAX_CHECKPOINTS,
    CODEX_HARVEST_MAX_CONTEXT_BYTES,
    CODEX_HARVEST_MAX_CONTEXT_MESSAGES,
    CODEX_HARVEST_MAX_ENTRIES,
    CODEX_HARVEST_MAX_EVENTS,
    CODEX_HARVEST_MAX_FILE_BYTES,
    CODEX_HARVEST_MAX_FILES,
    CODEX_HARVEST_MAX_FOCUS_BYTES,
    CODEX_HARVEST_MAX_LINE_BYTES,
    CODEX_HARVEST_MAX_RECORDS,
    CODEX_HARVEST_MAX_RESERVOIR,
    CODEX_HARVEST_MAX_TOTAL_BYTES,
    CODEX_HARVEST_MAX_WALL_SECONDS,
    CODEX_HARVEST_PROTOCOL_VERSION,
)
from ynoy.models.base import DataClass, StrictModel
from ynoy.util import canonical_sha256, sha256_text

HarvestSignal = Literal[
    "decision",
    "correction",
    "evidence_demand",
    "scope_change",
    "abstention",
    "outcome_feedback",
]
HarvestStatus = Literal["partial", "audit_ready", "complete", "complete_insufficient"]


class HarvestLimits(StrictModel):
    max_files: int = Field(default=CODEX_HARVEST_MAX_FILES, ge=1, le=64)
    max_total_input_bytes: int = Field(default=CODEX_HARVEST_MAX_TOTAL_BYTES, ge=1)
    max_file_bytes: int = Field(default=CODEX_HARVEST_MAX_FILE_BYTES, ge=1)
    max_line_bytes: int = Field(default=CODEX_HARVEST_MAX_LINE_BYTES, ge=1)
    max_records: int = Field(default=CODEX_HARVEST_MAX_RECORDS, ge=1)
    max_events: int = Field(default=CODEX_HARVEST_MAX_EVENTS, ge=1)
    max_wall_seconds: float = Field(default=CODEX_HARVEST_MAX_WALL_SECONDS, gt=0.0)
    max_reservoir: int = Field(
        default=CODEX_HARVEST_MAX_RESERVOIR, ge=1, le=CODEX_HARVEST_MAX_RESERVOIR
    )
    max_context_messages: int = Field(default=CODEX_HARVEST_MAX_CONTEXT_MESSAGES, ge=1, le=16)
    max_context_bytes: int = Field(default=CODEX_HARVEST_MAX_CONTEXT_BYTES, ge=1)
    max_focus_bytes: int = Field(default=CODEX_HARVEST_MAX_FOCUS_BYTES, ge=1)
    max_artifact_bytes: int = Field(default=CODEX_HARVEST_MAX_ARTIFACT_BYTES, ge=1)
    max_checkpoints: int = Field(default=CODEX_HARVEST_MAX_CHECKPOINTS, ge=1)
    max_entries: int = Field(default=CODEX_HARVEST_MAX_ENTRIES, ge=1)

    @model_validator(mode="after")
    def limits_are_coherent(self) -> HarvestLimits:
        if self.max_file_bytes > self.max_total_input_bytes:
            raise ValueError("harvest file limit cannot exceed total input limit")
        if self.max_line_bytes > self.max_file_bytes:
            raise ValueError("harvest line limit cannot exceed file limit")
        if self.max_focus_bytes > self.max_artifact_bytes:
            raise ValueError("harvest focus limit cannot exceed artifact limit")
        if self.max_context_bytes > self.max_artifact_bytes:
            raise ValueError("harvest context limit cannot exceed artifact limit")
        return self

    @property
    def config_sha256(self) -> str:
        return canonical_sha256(
            {
                "protocol": CODEX_HARVEST_PROTOCOL_VERSION,
                "limits": self.model_dump(mode="json"),
                "selector": "judgment-signals/0.1",
                "tie_order": "score-desc/keyed-sha256",
            }
        )


class HarvestContextMessage(StrictModel):
    speaker: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_matches(self) -> HarvestContextMessage:
        if sha256_text(self.content) != self.content_sha256:
            raise ValueError("harvest context hash does not match content")
        return self


class HarvestCandidate(StrictModel):
    candidate_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: Literal["sessions", "archived_sessions"]
    session_month: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    blob_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_start: int = Field(ge=0)
    byte_length: int = Field(ge=1)
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    turn_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    signal_score: int = Field(ge=1)
    signal_tags: tuple[HarvestSignal, ...] = Field(min_length=1)
    context: tuple[HarvestContextMessage, ...]
    focus: str = Field(min_length=1)
    focus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_holder: Literal["unknown"] = "unknown"
    source_authority: Literal["user_turn_unattributed"] = "user_turn_unattributed"
    attribution_status: Literal["awaiting_represented_user_review"] = (
        "awaiting_represented_user_review"
    )
    lineage_completeness: Literal["partial_root_session"] = "partial_root_session"
    benchmark_eligible: Literal[False] = False
    core_eligible: Literal[False] = False
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def candidate_contract_matches(self) -> HarvestCandidate:
        if self.focus_sha256 != sha256_text(self.focus):
            raise ValueError("harvest focus hash does not match content")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"candidate_sha256"}))
        if self.candidate_sha256 != expected:
            raise ValueError("harvest candidate receipt does not match payload")
        return self


class HarvestFileCursor(StrictModel):
    partition: Literal["sessions", "archived_sessions"]
    relative_locator: str = Field(min_length=1)
    sort_key: str = Field(min_length=1)
    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    blob_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_bytes: int = Field(ge=1)
    modified_ns: int = Field(ge=1)
    device: int = Field(ge=0)
    inode: int = Field(ge=0)
    next_byte_offset: int = Field(ge=0)
    completed_lines: int = Field(ge=0)
    complete: bool

    @model_validator(mode="after")
    def offset_matches_file(self) -> HarvestFileCursor:
        if self.next_byte_offset > self.file_bytes:
            raise ValueError("harvest cursor exceeds its file")
        if self.complete != (self.next_byte_offset == self.file_bytes):
            raise ValueError("harvest cursor completion contradicts its offset")
        return self


class HarvestCursor(StrictModel):
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stable_before_ns: int = Field(ge=1)
    selector_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    last_file: HarvestFileCursor | None = None
    status: Literal["partial", "complete"]
    cursor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def cursor_receipt_matches(self) -> HarvestCursor:
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"cursor_sha256"}))
        if self.cursor_sha256 != expected:
            raise ValueError("harvest cursor receipt does not match payload")
        return self


class HarvestCheckpoint(StrictModel):
    protocol_version: Literal["codex-judgment-harvest/0.1"] = CODEX_HARVEST_PROTOCOL_VERSION
    cursor: HarvestCursor
    candidates: tuple[HarvestCandidate, ...]
    exclusion_counts: dict[str, int]
    checkpoint_input_bytes: int = Field(ge=0)
    checkpoint_record_count: int = Field(ge=0)
    checkpoint_event_count: int = Field(ge=0)
    checkpoint_file_count: int = Field(ge=0)
    status: HarvestStatus
    model_provider_used: Literal[False] = False
    database_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def checkpoint_receipt_matches(self) -> HarvestCheckpoint:
        if len(self.candidates) > CODEX_HARVEST_MAX_RESERVOIR:
            raise ValueError("harvest checkpoint exceeds the hard reservoir limit")
        if len(self.exclusion_counts) > 64 or any(
            not isinstance(value, int) or value < 0 for value in self.exclusion_counts.values()
        ):
            raise ValueError("harvest exclusions exceed their bounded counter contract")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"checkpoint_sha256"}))
        if self.checkpoint_sha256 != expected:
            raise ValueError("harvest checkpoint receipt does not match payload")
        return self


class HarvestManifest(StrictModel):
    protocol_version: Literal["codex-judgment-harvest/0.1"] = CODEX_HARVEST_PROTOCOL_VERSION
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_boundary_session_start_ns: int = Field(ge=1)
    stable_before_ns: int = Field(ge=1)
    selector_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    limits: HarvestLimits
    created_at: datetime
    expires_at: datetime
    source_data_class: DataClass
    synthetic: bool
    progressive_source_not_frozen_snapshot: Literal[True] = True
    holdout_labels_used: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    model_provider_used: Literal[False] = False
    database_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def manifest_contract_matches(self) -> HarvestManifest:
        if self.expires_at <= self.created_at:
            raise ValueError("harvest retention must end after creation")
        if self.stable_before_ns >= self.holdout_boundary_session_start_ns:
            raise ValueError("harvest stability cutoff must precede the holdout boundary")
        expected_class = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.source_data_class != expected_class:
            raise ValueError("harvest data class contradicts its mode")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"manifest_sha256"}))
        if self.manifest_sha256 != expected:
            raise ValueError("harvest manifest receipt does not match payload")
        return self
