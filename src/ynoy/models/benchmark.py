from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ynoy.models.base import DataClass, DecisionLabel, EvidenceRegime, RecordBase, StrictModel


class BenchmarkCase(RecordBase):
    case_id: str
    domain: str = "coding_judgment"
    task_type: str
    decision_class: str
    event_time: datetime
    dependency_cluster_id: str
    task_context: str
    evidence: tuple[str, ...] = ()
    declared_profile: tuple[str, ...] = ()
    structured_core: tuple[str, ...] = ()
    hidden_target: DecisionLabel
    hidden_rationale_terms: tuple[str, ...] = ()
    data_class: Literal[DataClass.PUBLIC_SYNTHETIC] = DataClass.PUBLIC_SYNTHETIC
    synthetic: Literal[True] = True
    challenge_tags: tuple[str, ...] = ()


class BenchmarkPredictorInput(StrictModel):
    case_id: str
    domain: str
    task_type: str
    decision_class: str
    event_time: datetime
    dependency_cluster_id: str
    task_context: str
    evidence: tuple[str, ...] = ()
    declared_profile: tuple[str, ...] = ()
    structured_core: tuple[str, ...] = ()
    data_class: Literal[DataClass.PUBLIC_SYNTHETIC] = DataClass.PUBLIC_SYNTHETIC
    synthetic: Literal[True] = True
    challenge_tags: tuple[str, ...] = ()


class BenchmarkManifest(RecordBase):
    name: str
    case_ids: tuple[str, ...]
    development_case_ids: tuple[str, ...]
    sealed_case_ids: tuple[str, ...]
    dependency_clusters: tuple[str, ...]
    temporal_cutoff: datetime
    case_set_sha256: str
    protocol_sha256: str
    algorithms: tuple[str, ...]
    regimes: tuple[EvidenceRegime, ...]
    sealed: Literal[True] = True
    manifest_sha256: str = ""


class Prediction(StrictModel):
    case_id: str
    algorithm: str
    regime: EvidenceRegime
    predicted_label: DecisionLabel
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool
    evidence_receipts: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    fatal_gate: str | None = None


class BenchmarkRun(RecordBase):
    manifest_id: UUID
    manifest_sha256: str
    status: Literal["complete", "invalid"]
    predictions: tuple[Prediction, ...]
    metrics: dict[str, dict[str, float | int | str | bool]]
    fatal_gates: tuple[str, ...] = ()
    local_only: bool = True
    external_calls: tuple[str, ...] = ()
    evidence_tier: Literal["mock/support"] = "mock/support"
    acceptance_status: Literal["not_calibrated", "failed_fatal_gate"] = "not_calibrated"
    run_sha256: str = ""
