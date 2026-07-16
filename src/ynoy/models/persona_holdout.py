from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, StrictModel
from ynoy.models.codex_inventory import CodexPartition
from ynoy.util import canonical_sha256


class HoldoutSourceReceipt(StrictModel):
    source_receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage_component_receipt: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition: CodexPartition
    file_bytes: int = Field(ge=1)
    session_start_ns: int = Field(ge=1)


class ProtectedHoldoutFreeze(StrictModel):
    protocol_version: Literal["persona-holdout-freeze/0.1"] = "persona-holdout-freeze/0.1"
    freeze_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    annotation_selection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_max_session_start_ns: int = Field(ge=1)
    boundary_session_start_ns: int = Field(ge=1)
    sources: tuple[HoldoutSourceReceipt, ...] = Field(min_length=8, max_length=12)
    selected_file_count: int = Field(ge=8, le=12)
    selected_input_bytes: int = Field(ge=1)
    metadata_record_opened: Literal[True] = True
    dialogue_content_opened: Literal[False] = False
    target_labels_created: Literal[False] = False
    predictor_access_granted: Literal[False] = False
    annotation_source_overlap: Literal[False] = False
    explicit_lineage_overlap: Literal[False] = False
    duplicate_content_overlap_status: Literal["unchecked_until_sealed_open"] = (
        "unchecked_until_sealed_open"
    )
    ordering_basis: Literal["canonical_rollout_filename_time"] = "canonical_rollout_filename_time"
    event_time_order_verified: Literal[False] = False
    source_data_class: DataClass
    database_used: Literal[False] = False
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def freeze_contract_matches(self) -> ProtectedHoldoutFreeze:
        if self.selected_file_count != len(self.sources):
            raise ValueError("holdout source count does not match its freeze")
        if self.selected_input_bytes != sum(item.file_bytes for item in self.sources):
            raise ValueError("holdout byte count does not match its freeze")
        if any(item.session_start_ns < self.boundary_session_start_ns for item in self.sources):
            raise ValueError("holdout sources must follow the frozen session-start boundary")
        if self.annotation_max_session_start_ns >= self.boundary_session_start_ns:
            raise ValueError("annotation sessions must strictly precede protected holdout sessions")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"freeze_sha256"}))
        if self.freeze_sha256 != expected:
            raise ValueError("protected holdout freeze receipt does not match its payload")
        return self
