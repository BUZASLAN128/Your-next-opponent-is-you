from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ynoy.util import new_id, utc_now


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


class DataClass(StrEnum):
    PUBLIC_SYNTHETIC = "D0"
    PRIVATE_TASK = "D1"
    RAW_CORPUS = "D2"
    DERIVED_IDENTITY = "D3"
    CREDENTIAL = "D4"
    THIRD_PARTY_PERSONAL = "D5"


class Speaker(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class SourceAuthority(StrEnum):
    EXPLICIT_USER_STATEMENT = "explicit_user_statement"
    USER_TURN_UNATTRIBUTED = "user_turn_unattributed"
    USER_BEHAVIOR = "user_behavior"
    ASSISTANT_CONTEXT = "assistant_context"
    THIRD_PARTY_CONTEXT = "third_party_context"
    EXTERNAL_HYPOTHESIS = "external_hypothesis"
    SYSTEM_CONTROL = "system_control"
    UNKNOWN = "unknown"


class ClaimHolder(StrEnum):
    REPRESENTED_USER = "represented_user"
    ASSISTANT = "assistant"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class CandidateKind(StrEnum):
    TRAIT = "trait"
    VALUE = "value"
    NARRATIVE = "narrative"
    METACOGNITION = "metacognition"
    BELIEF = "belief"
    PREFERENCE = "preference"
    GOAL = "goal"
    RELATIONSHIP = "relationship"
    SKILL = "skill"


class DecisionLabel(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    CORRECT = "correct"
    DEFER = "defer"
    ASK = "ask"
    UNKNOWN = "unknown"


class Mode(StrEnum):
    MIRROR = "mirror"
    ADVISOR = "advisor"


class EvidenceRegime(StrEnum):
    ZERO = "zero"
    DECLARED = "declared"
    LOW = "low"
    HISTORY_RICH = "history_rich"


class ScopeRef(StrictModel):
    person_id: str = "self"
    project: str | None = None
    role: str | None = None
    audience: str | None = None
    risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def valid_interval(self) -> ScopeRef:
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until cannot precede valid_from")
        return self


class RecordBase(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    record_id: UUID = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
