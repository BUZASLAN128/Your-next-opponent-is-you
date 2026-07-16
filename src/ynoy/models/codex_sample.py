from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.constants import CODEX_CONTENT_PILOT_PARSER_VERSION, POLICY_VERSION
from ynoy.models.base import DataClass, StrictModel


class CodexContentPilotSummary(StrictModel):
    """Content-free receipt for one bounded, memory-only Codex parser run."""

    adapter: Literal["codex_local_content_pilot"] = "codex_local_content_pilot"
    parser_version: Literal["codex-local-content-pilot/0.1"] = CODEX_CONTENT_PILOT_PARSER_VERSION
    policy_version: str = POLICY_VERSION
    source_data_class: DataClass
    synthetic: bool
    selected_file_count: int = Field(ge=1)
    selected_input_bytes: int = Field(ge=1)
    scanned_record_count: int = Field(ge=1)
    normalized_event_count: int = Field(ge=0)
    selected_partition_counts: dict[str, int]
    selected_bucket_counts: dict[str, int]
    record_type_counts: dict[str, int]
    source_kind_counts: dict[str, int]
    speaker_counts: dict[str, int]
    excluded_counts: dict[str, int]
    repeated_content_cluster_count: int = Field(ge=0)
    explicit_parent_thread_count: int = Field(ge=0)
    max_files: int = Field(ge=1)
    max_total_input_bytes: int = Field(ge=1)
    max_file_bytes: int = Field(ge=1)
    max_line_bytes: int = Field(ge=1)
    max_records: int = Field(ge=1)
    max_events: int = Field(ge=1)
    max_content_bytes: int = Field(ge=1)
    normalized_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retention_mode: Literal["process_memory_only"] = "process_memory_only"
    deletion_mode: Literal["discarded_at_process_exit"] = "discarded_at_process_exit"
    interpretation_authority: Literal["none"] = "none"
    source_content_read: Literal[True] = True
    content_emitted: Literal[False] = False
    content_persisted: Literal[False] = False
    source_files_modified: Literal[False] = False
    private_artifact_written: Literal[False] = False
    database_used: Literal[False] = False
    model_provider_used: Literal[False] = False
    claims_derived: Literal[0] = 0
    annotation_records_created: Literal[0] = 0
    core_eligible: Literal[False] = False
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def bounded_counts_are_consistent(self) -> CodexContentPilotSummary:
        if self.selected_file_count > self.max_files:
            raise ValueError("selected files exceed the pilot limit")
        if self.selected_input_bytes > self.max_total_input_bytes:
            raise ValueError("selected input exceeds the pilot byte limit")
        if self.scanned_record_count > self.max_records:
            raise ValueError("scanned records exceed the pilot limit")
        if self.normalized_event_count > self.max_events:
            raise ValueError("normalized events exceed the pilot limit")
        expected_class = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.source_data_class != expected_class:
            raise ValueError("pilot data class contradicts its source mode")
        if sum(self.selected_partition_counts.values()) != self.selected_file_count:
            raise ValueError("partition counts do not match selected files")
        if sum(self.selected_bucket_counts.values()) != self.selected_file_count:
            raise ValueError("bucket counts do not match selected files")
        if sum(self.source_kind_counts.values()) != self.normalized_event_count:
            raise ValueError("source kind counts do not match normalized events")
        if sum(self.speaker_counts.values()) != self.normalized_event_count:
            raise ValueError("speaker counts do not match normalized events")
        if sum(self.record_type_counts.values()) != self.scanned_record_count:
            raise ValueError("record type counts do not match scanned records")
        if self.explicit_parent_thread_count > self.selected_file_count:
            raise ValueError("parent-thread counts exceed selected files")
        if self.repeated_content_cluster_count > self.normalized_event_count:
            raise ValueError("repeat clusters exceed normalized events")
        return self
