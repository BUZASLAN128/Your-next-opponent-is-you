from __future__ import annotations

from typing import Literal

from pydantic import Field

from ynoy.models.base import DataClass, EvidenceRegime, SourceAuthority, StrictModel
from ynoy.models.output import OutputEnvelope


class OperatingRule(StrictModel):
    rule_id: Literal[
        "evidence_honesty",
        "bounded_learning",
        "reversible_progress",
        "no_false_action",
    ]
    instruction: str = Field(min_length=1, max_length=240)
    source_authority: Literal[SourceAuthority.SYSTEM_CONTROL] = SourceAuthority.SYSTEM_CONTROL
    data_class: Literal[DataClass.PUBLIC_SYNTHETIC] = DataClass.PUBLIC_SYNTHETIC
    persona_evidence: Literal[False] = False


class OperatingMemorySeed(StrictModel):
    memory_kind: Literal["system_operating_seed"] = "system_operating_seed"
    seed_version: Literal["1.0"] = "1.0"
    evidence_regime: Literal[EvidenceRegime.ZERO] = EvidenceRegime.ZERO
    persona_memory_state: Literal["empty"] = "empty"
    persona_evidence_count: Literal[0] = 0
    source_authority: Literal[SourceAuthority.SYSTEM_CONTROL] = SourceAuthority.SYSTEM_CONTROL
    data_class: Literal[DataClass.PUBLIC_SYNTHETIC] = DataClass.PUBLIC_SYNTHETIC
    persistence: Literal["ephemeral"] = "ephemeral"
    automatic_core_promotion: Literal[False] = False
    rules: tuple[OperatingRule, ...]


class ManagerStartResult(StrictModel):
    status: Literal["ready"] = "ready"
    task_data_class: Literal[DataClass.PRIVATE_TASK] = DataClass.PRIVATE_TASK
    database_used: Literal[False] = False
    provider_used: Literal[False] = False
    persistence_status: Literal["not_persisted"] = "not_persisted"
    audit_status: Literal["not_persisted_no_database"] = "not_persisted_no_database"
    operating_memory: OperatingMemorySeed
    advisory: OutputEnvelope
