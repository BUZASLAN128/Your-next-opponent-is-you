from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ynoy.direct_memory import AuthorizationIntent, ProvenanceState
from ynoy.models import Speaker
from ynoy.models.base import StrictModel


class ExactInput(StrictModel):
    source_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    said_at: datetime | None
    exact_text: str = Field(min_length=1)


class ImportedInput(ExactInput):
    speaker: Speaker


class LiveInput(ExactInput):
    subject_id: str = "self"
    authorization_intent: AuthorizationIntent | None = None


class ToolInput(StrictModel):
    source_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    inputs: dict[str, object]
    result: dict[str, object]


class ClaimInput(StrictModel):
    project: str = Field(min_length=1)
    fact_key: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    state: ProvenanceState
    payload: dict[str, object]
    event_time: datetime | None = None
    tool_receipt_id: str | None = None
    subject_id: str = "self"
