from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from ynoy.constants import POLICY_VERSION
from ynoy.models.base import DataClass, Mode, RecordBase, StrictModel
from ynoy.util import new_id


class OutputEnvelope(StrictModel):
    mode: Mode
    mission: Literal["coding_judgment"] = "coding_judgment"
    answer: str
    answer_kind: Literal["system_advisory", "untrusted_reasoner_advisory"] = "system_advisory"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_receipts: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    authority: Literal["none"] = "none"
    proposed_action: str | None = None
    action_status: Literal["not_performed"] = "not_performed"
    action_receipt: None = None
    personal_fit: Literal["known", "partial", "unknown"] = "unknown"
    question: str | None = None


class EgressEnvelope(StrictModel):
    request_id: UUID = Field(default_factory=new_id)
    destination: str
    purpose: str
    data_classes: frozenset[DataClass]
    selected_fields: tuple[str, ...]
    byte_upper_bound: Annotated[int, Field(gt=0)]
    policy_version: str = POLICY_VERSION
    retention_assumption: str
    approval_receipt: str | None = None


class AuditReceipt(RecordBase):
    event_type: Literal[
        "inventory",
        "approval",
        "ingest",
        "derive",
        "report",
        "egress_decision",
        "provider_call",
        "erasure_plan",
        "erasure_confirm",
        "error",
    ]
    actor_class: str
    policy_version: str = POLICY_VERSION
    parser_version: str | None = None
    config_version: str
    opaque_input_ids: tuple[str, ...] = ()
    input_count: int = Field(ge=0)
    data_classes: tuple[DataClass, ...] = ()
    decision: Literal["allow", "deny", "partial", "complete", "invalidated"]
    reason_code: str
    destination: str | None = None
    retention_class: str | None = None
    artifact_id: str | None = None
    status: Literal["success", "failure", "partial"]
