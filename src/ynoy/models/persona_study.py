from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from ynoy.constants import PERSONA_STUDY_PROTOCOL_VERSION
from ynoy.models.base import ClaimHolder, DataClass, SourceAuthority, Speaker, StrictModel
from ynoy.util import canonical_sha256, sha256_text


class StudyMessage(StrictModel):
    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    speaker: Speaker
    structural_claim_holder: ClaimHolder
    source_authority: SourceAuthority
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_time: datetime | None = None
    sequence_index: int = Field(ge=1)

    @model_validator(mode="after")
    def content_receipt_matches(self) -> StudyMessage:
        if self.content_sha256 != sha256_text(self.content):
            raise ValueError("study message hash does not match exact content")
        return self


class PresentationMessage(StrictModel):
    speaker: Speaker
    content: str = Field(min_length=1)


class EvidenceWindow(StrictModel):
    protocol_version: Literal["persona-study/0.1"] = PERSONA_STUDY_PROTOCOL_VERSION
    window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_dependencies: tuple[str, ...] = Field(min_length=1)
    conversation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_thread_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    turn_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    dependency_component_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_path_status: Literal["unknown"] = "unknown"
    lineage_completeness: Literal["partial", "unknown"]
    selection_arm: Literal["sampled", "challenge"]
    challenge_tags: tuple[str, ...] = ()
    context: tuple[StudyMessage, ...] = Field(max_length=4)
    focus: StudyMessage
    source_data_class: DataClass
    interpretation_authority: Literal["none"] = "none"
    core_eligible: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    window_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def evidence_contract_is_consistent(self) -> EvidenceWindow:
        if self.focus.speaker != Speaker.USER:
            raise ValueError("persona-study focus must be a structural user turn")
        if self.focus.structural_claim_holder != ClaimHolder.UNKNOWN:
            raise ValueError("unreviewed focus cannot claim represented-user authorship")
        if self.focus.source_authority != SourceAuthority.USER_TURN_UNATTRIBUTED:
            raise ValueError("unreviewed focus must retain unattributed user-turn authority")
        if any(item.sequence_index >= self.focus.sequence_index for item in self.context):
            raise ValueError("study context must strictly precede the focus turn")
        if self.focus.event_time is not None and any(
            item.event_time is not None and item.event_time > self.focus.event_time
            for item in self.context
        ):
            raise ValueError("study context time must precede the focus turn")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"window_sha256"}))
        if self.window_sha256 != expected:
            raise ValueError("evidence-window receipt does not match its payload")
        return self


class AnnotationPresentation(StrictModel):
    protocol_version: Literal["persona-study/0.1"] = PERSONA_STUDY_PROTOCOL_VERSION
    presentation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    order: int = Field(ge=1, le=32)
    context: tuple[PresentationMessage, ...] = Field(max_length=4)
    focus: PresentationMessage
    interpretation_authority: Literal["represented_user_only"] = "represented_user_only"
    model_suggestion_visible: Literal[False] = False


class BlindMapEntry(StrictModel):
    presentation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_partition: Literal["annotation_development", "annotation_reserved"]
    repeated: bool


class PersonaStudyManifest(StrictModel):
    protocol_version: Literal["persona-study/0.1"] = PERSONA_STUDY_PROTOCOL_VERSION
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blind_map_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cutoff: datetime
    created_at: datetime
    expires_at: datetime
    unique_window_count: Literal[24] = 24
    presentation_count: Literal[32] = 32
    blind_repeat_count: Literal[8] = 8
    selected_file_count: Literal[24] = 24
    selected_input_bytes: int = Field(ge=1)
    scanned_record_count: int = Field(ge=1)
    normalized_event_count: int = Field(ge=24)
    annotation_development_count: int = Field(ge=8, le=16)
    annotation_reserved_count: int = Field(ge=8, le=16)
    dependency_component_count: int = Field(ge=6)
    baseline_names: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    thresholds: dict[str, float | int]
    deletion_proof_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    protected_holdout_freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    independent_source_replay_verified: Literal[True] = True
    retention_enforcement: Literal["on_access"] = "on_access"
    background_deletion_guaranteed: Literal[False] = False
    protected_holdout_claimed: Literal[True] = True
    status: Literal["awaiting_represented_user_labels"] = "awaiting_represented_user_labels"
    source_data_class: DataClass
    derived_data_class: Literal[DataClass.DERIVED_IDENTITY] = DataClass.DERIVED_IDENTITY
    database_used: Literal[False] = False
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def manifest_contract_is_consistent(self) -> PersonaStudyManifest:
        if self.expires_at <= self.created_at:
            raise ValueError("persona-study expiry must follow creation")
        if self.annotation_development_count + self.annotation_reserved_count != 24:
            raise ValueError("annotation partitions must cover every unique window")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"manifest_sha256"}))
        if self.manifest_sha256 != expected:
            raise ValueError("persona-study manifest receipt does not match its payload")
        return self


class StudyArtifactEntry(StrictModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_class: DataClass
    source_dependencies: tuple[str, ...]
    mutable_by: Literal["none", "represented_user"] = "none"


class StudyArtifactIndex(StrictModel):
    study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    expires_at: datetime
    entries: tuple[StudyArtifactEntry, ...] = Field(min_length=1)
    index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def index_contract_is_consistent(self) -> StudyArtifactIndex:
        paths = tuple(item.relative_path for item in self.entries)
        invalid = any(
            "\\" in item or item.startswith("/") or ".." in item.split("/") for item in paths
        )
        if len(paths) != len(set(paths)) or invalid:
            raise ValueError("artifact index paths must be unique relative POSIX paths")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"index_sha256"}))
        if self.index_sha256 != expected:
            raise ValueError("artifact index receipt does not match its payload")
        return self


class DeletionProofReceipt(StrictModel):
    proof_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_dependency: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    regenerated_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_deleted_count: int = Field(ge=1)
    second_deleted_count: int = Field(ge=1)
    read_after_delete: Literal["not_found"] = "not_found"
    source_deleted: Literal[False] = False
    physical_erase_claimed: Literal[False] = False
    derived_closure_complete: Literal[True] = True
    created_at: datetime
    expires_at: datetime
    retention_enforcement: Literal["on_access"] = "on_access"
    background_deletion_guaranteed: Literal[False] = False

    @model_validator(mode="after")
    def retention_window_is_valid(self) -> DeletionProofReceipt:
        retention = self.expires_at - self.created_at
        if retention <= timedelta(0) or retention > timedelta(days=7):
            raise ValueError("deletion receipt retention must not exceed seven days")
        return self
