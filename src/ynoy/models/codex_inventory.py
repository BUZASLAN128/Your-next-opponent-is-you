from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, RecordBase, StrictModel

CodexPartition = Literal["sessions", "archived_sessions"]
FirstRecordState = Literal[
    "session_meta",
    "empty",
    "invalid_first_record",
    "oversized_first_record",
]


class CodexInventoryEntry(StrictModel):
    """Privacy-minimized metadata for one canonical Codex session file."""

    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: CodexPartition
    file_bytes: int = Field(ge=0)
    observed_month: str | None = Field(default=None, pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    first_record_state: FirstRecordState


class CodexMonthSummary(StrictModel):
    month: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    file_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)


class CodexMetadataInventory(RecordBase):
    """Checksum-bound private manifest without conversation fields or paths."""

    adapter: Literal["codex_local_sessions_metadata"] = "codex_local_sessions_metadata"
    parser_version: Literal["codex-local-metadata/1.0"] = "codex-local-metadata/1.0"
    policy_version: Literal["egress-and-authority/1.0"] = "egress-and-authority/1.0"
    source_data_class: DataClass
    synthetic: bool
    scan_scope: tuple[CodexPartition, ...] = ("sessions", "archived_sessions")
    excluded_scope: tuple[str, ...] = (
        "credential_stores",
        "backup_trees",
        "noncanonical_codex_paths",
        "message_and_tool_content",
    )
    entries: tuple[CodexInventoryEntry, ...]
    entry_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    ignored_noncanonical_file_count: int = Field(ge=0)
    partition_counts: dict[str, int]
    state_counts: dict[str, int]
    monthly: tuple[CodexMonthSummary, ...]
    content_fields_copied: Literal[False] = False
    claims_derived: Literal[0] = 0
    metadata_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(default="", pattern=r"^$|^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def metadata_contract_is_consistent(self) -> CodexMetadataInventory:
        if self.scan_scope != ("sessions", "archived_sessions"):
            raise ValueError("Codex inventory scope must stay canonical and explicit")
        expected_class = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.source_data_class != expected_class:
            raise ValueError("Codex inventory data class contradicts its source mode")
        if len({item.source_key for item in self.entries}) != len(self.entries):
            raise ValueError("Codex inventory source keys must be unique")
        if self.entry_count != len(self.entries):
            raise ValueError("Codex inventory entry count does not match entries")
        if self.total_bytes != sum(item.file_bytes for item in self.entries):
            raise ValueError("Codex inventory byte count does not match entries")
        partitions = Counter(item.partition for item in self.entries)
        states = Counter(item.first_record_state for item in self.entries)
        if self.partition_counts != dict(sorted(partitions.items())):
            raise ValueError("Codex inventory partition counts do not match entries")
        if self.state_counts != dict(sorted(states.items())):
            raise ValueError("Codex inventory state counts do not match entries")
        expected_months: dict[str, tuple[int, int]] = {}
        for item in self.entries:
            if item.observed_month:
                count, size = expected_months.get(item.observed_month, (0, 0))
                expected_months[item.observed_month] = (count + 1, size + item.file_bytes)
        actual_months = {item.month: (item.file_count, item.total_bytes) for item in self.monthly}
        if actual_months != expected_months or len(actual_months) != len(self.monthly):
            raise ValueError("Codex inventory month summaries do not match entries")
        return self
