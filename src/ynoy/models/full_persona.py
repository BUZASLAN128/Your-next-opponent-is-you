from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.full_persona_exclusion import (
    FullCorpusExclusion,
    exclusion_order,
    validate_exclusion_reasons,
)
from ynoy.models.full_persona_source import FullCorpusSource as FullCorpusSource
from ynoy.util import canonical_sha256, sha256_text

type Digest = str


class EvidenceRole(StrEnum):
    DIRECT = "direct_user_expression"
    PROJECT = "project_instruction"
    MIXED = "mixed_authored_and_imported"


class FullCorpusLimits(StrictModel):
    max_manifest_files: int = Field(default=100_000, ge=1, le=100_000)
    max_manifest_input_bytes: int = Field(default=80 * 1024**3, ge=1)
    max_manifest_control_bytes: int = Field(default=16 * 1024**2, ge=1024, le=16 * 1024**2)
    source_chunk_bytes: int = Field(default=4 * 1024**2, ge=64 * 1024, le=16 * 1024**2)
    max_line_bytes: int = Field(default=1024**2, ge=1)
    max_wire_record_bytes: int = Field(default=64 * 1024**2, ge=1)
    max_evidence_bytes: int = Field(default=128 * 1024, ge=1)
    max_context_messages: int = Field(default=4, ge=0, le=16)
    max_context_bytes: int = Field(default=8 * 1024, ge=0)
    max_shard_records: int = Field(default=2_000, ge=1, le=20_000)
    max_shard_uncompressed_bytes: int = Field(default=4 * 1024**2, ge=1024)
    max_checkpoint_input_bytes: int = Field(default=256 * 1024**2, ge=1024)
    max_run_output_bytes: int = Field(default=8 * 1024**3, ge=1024)
    retention_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def limits_are_coherent(self) -> FullCorpusLimits:
        if self.max_line_bytes > self.max_wire_record_bytes:
            raise ValueError("line limit cannot exceed the hard wire-record limit")
        if self.max_context_bytes > self.max_shard_uncompressed_bytes:
            raise ValueError("context limit cannot exceed the shard limit")
        return self

    @property
    def config_sha256(self) -> Digest:
        return canonical_sha256(
            {"protocol": "full-persona-corpus/0.2", "limits": self.model_dump(mode="json")}
        )


class FullCorpusManifest(StrictModel):
    protocol_version: Literal["full-persona-corpus/0.2"] = "full-persona-corpus/0.2"
    run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_study_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_freeze_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_boundary_session_start_ns: int = Field(ge=1)
    stable_before_ns: int = Field(ge=1)
    created_at: datetime
    expires_at: datetime
    limits: FullCorpusLimits
    source_data_class: DataClass
    synthetic: bool
    files: tuple[FullCorpusSource, ...] = Field(min_length=1)
    expected_file_count: int = Field(ge=1)
    expected_input_bytes: int = Field(ge=1)
    source_snapshot_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    excluded_files: tuple[FullCorpusExclusion, ...]
    expected_excluded_file_count: int = Field(ge=0)
    exclusion_snapshot_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_labels_used: Literal[False] = False
    database_used: Literal[False] = False
    external_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def manifest_is_complete(self) -> FullCorpusManifest:
        expected_class = DataClass.PUBLIC_SYNTHETIC if self.synthetic else DataClass.RAW_CORPUS
        if self.source_data_class != expected_class:
            raise ValueError("full-corpus manifest data class contradicts its mode")
        if self.expires_at <= self.created_at:
            raise ValueError("full-corpus retention must end after creation")
        if self.expected_file_count != len(self.files):
            raise ValueError("full-corpus file count does not reconcile")
        if self.expected_input_bytes != sum(item.file_bytes for item in self.files):
            raise ValueError("full-corpus input bytes do not reconcile")
        if self.expected_excluded_file_count != len(self.excluded_files):
            raise ValueError("full-corpus exclusion count does not reconcile")
        if self.expected_file_count > self.limits.max_manifest_files:
            raise ValueError("full-corpus manifest exceeds its file limit")
        if self.expected_input_bytes > self.limits.max_manifest_input_bytes:
            raise ValueError("full-corpus manifest exceeds its input-byte limit")
        ordered = tuple(sorted(self.files, key=_source_order))
        if self.files != ordered or len({item.source_key for item in self.files}) != len(
            self.files
        ):
            raise ValueError("full-corpus sources must be ordered and unique")
        exclusions = tuple(sorted(self.excluded_files, key=exclusion_order))
        excluded_keys = {item.source_key for item in exclusions}
        if self.excluded_files != exclusions or len(excluded_keys) != len(exclusions):
            raise ValueError("full-corpus exclusions must be ordered and unique")
        if excluded_keys & {item.source_key for item in self.files}:
            raise ValueError("full-corpus source cannot also be excluded")
        if any(item.modified_ns > self.stable_before_ns for item in self.files):
            raise ValueError("full-corpus source exceeds its stability cutoff")
        validate_exclusion_reasons(self.excluded_files, self.stable_before_ns)
        snapshot = canonical_sha256([item.model_dump(mode="json") for item in self.files])
        if self.source_snapshot_sha256 != snapshot:
            raise ValueError("full-corpus source snapshot hash does not match")
        exclusion_snapshot = canonical_sha256(
            [item.model_dump(mode="json") for item in self.excluded_files]
        )
        if self.exclusion_snapshot_sha256 != exclusion_snapshot:
            raise ValueError("full-corpus exclusion snapshot hash does not match")
        _require_hash(self, "manifest_sha256")
        return self


class FullCorpusContext(StrictModel):
    speaker: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_matches(self) -> FullCorpusContext:
        if self.content_sha256 != sha256_text(self.content):
            raise ValueError("full-corpus context hash does not match")
        return self


class FullCorpusEvidence(StrictModel):
    evidence_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    blob_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    byte_start: int = Field(ge=0)
    byte_length: int = Field(ge=1)
    line_number: int = Field(ge=1)
    record_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    turn_key: Digest | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_time: datetime
    time_basis: Literal["event", "session_start"]
    role: EvidenceRole
    signal_tags: tuple[str, ...]
    context: tuple[FullCorpusContext, ...]
    content: str = Field(min_length=1)
    content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    authorship_status: Literal["corpus_owner_confirmed_structural_turn"] = (
        "corpus_owner_confirmed_structural_turn"
    )
    semantic_adoption: Literal["not_established"] = "not_established"
    core_eligible: Literal[False] = False
    evidence_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def evidence_hash_matches(self) -> FullCorpusEvidence:
        if self.content_sha256 != sha256_text(self.content):
            raise ValueError("full-corpus evidence content hash does not match")
        _require_hash(self, "evidence_sha256")
        return self


class FullCorpusHead(StrictModel):
    protocol_version: Literal["full-persona-head/0.1"] = "full-persona-head/0.1"
    run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=0)
    status: Literal["frozen", "scanning", "complete"]
    file_index: int = Field(ge=0)
    next_byte_offset: int = Field(ge=0)
    completed_lines: int = Field(ge=0)
    parser_state: dict[str, Any]
    context: tuple[FullCorpusContext, ...]
    processed_input_bytes: int = Field(ge=0)
    processed_record_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    quarantined_count: int = Field(ge=0)
    current_file_record_count: int = Field(ge=0)
    current_file_evidence_count: int = Field(ge=0)
    current_file_quarantined_count: int = Field(ge=0)
    current_file_exclusion_counts: dict[str, int]
    shard_count: int = Field(ge=0)
    output_bytes: int = Field(ge=0)
    exclusion_counts: dict[str, int]
    previous_head_sha256: Digest | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    last_shard_sha256: Digest | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def head_hash_matches(self) -> FullCorpusHead:
        if (
            len(self.parser_state) > 8
            or len(self.exclusion_counts) > 64
            or len(self.current_file_exclusion_counts) > 64
        ):
            raise ValueError("full-corpus head exceeds its bounded state contract")
        if any(
            value < 0
            for value in (
                *self.exclusion_counts.values(),
                *self.current_file_exclusion_counts.values(),
            )
        ):
            raise ValueError("full-corpus exclusions cannot be negative")
        if self.revision == 0 and self.previous_head_sha256 is not None:
            raise ValueError("initial full-corpus head cannot have a parent")
        if self.shard_count == 0 and self.last_shard_sha256 is not None:
            raise ValueError("head without shards cannot bind a last shard")
        _require_hash(self, "head_sha256")
        return self


class FullCorpusShardReceipt(StrictModel):
    run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    relative_path: str = Field(pattern=r"^shards/[0-9]{8}\.jsonl\.gz$")
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    start_byte_offset: int = Field(ge=0)
    end_byte_offset: int = Field(ge=0)
    start_line_number: int = Field(ge=0)
    end_line_number: int = Field(ge=0)
    evidence_count: int = Field(ge=1)
    uncompressed_bytes: int = Field(ge=1)
    compressed_bytes: int = Field(ge=1)
    content_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def shard_receipt_matches(self) -> FullCorpusShardReceipt:
        if self.end_byte_offset <= self.start_byte_offset:
            raise ValueError("full-corpus shard offsets do not advance")
        if self.end_line_number < self.start_line_number:
            raise ValueError("full-corpus shard line range is invalid")
        _require_hash(self, "receipt_sha256")
        return self


class FullCorpusFileReceipt(StrictModel):
    run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    file_index: int = Field(ge=0)
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    blob_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    processed_bytes: int = Field(ge=1)
    record_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    quarantined_count: int = Field(ge=0)
    exclusion_counts: dict[str, int]
    status: Literal["complete", "remainder_excluded"]
    receipt_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def file_receipt_matches(self) -> FullCorpusFileReceipt:
        if len(self.exclusion_counts) > 64 or any(
            value < 0 for value in self.exclusion_counts.values()
        ):
            raise ValueError("full-corpus file exclusions are invalid")
        _require_hash(self, "receipt_sha256")
        return self


def _source_order(value: FullCorpusSource) -> tuple[int, str, str]:
    return value.session_start_ns, value.partition, value.source_key


def _require_hash(model: StrictModel, field: str) -> None:
    payload = model.model_dump(mode="json", exclude={field})
    if getattr(model, field) != canonical_sha256(payload):
        raise ValueError(f"{field} does not match its canonical payload")
