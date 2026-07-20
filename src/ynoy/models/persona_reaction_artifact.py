from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_reaction_benchmark import PersonaReactionBaselineRun
from ynoy.models.persona_reaction_results import (
    PersonaReactionComparisonResult,
    PersonaReactionModelRun,
    PersonaReactionPredictionFreeze,
    PersonaReactionTargetSet,
)
from ynoy.util import canonical_sha256

type Digest = str


class PersonaReactionBenchmarkArtifact(StrictModel):
    protocol_version: Literal["persona-reaction-artifact/0.1"] = "persona-reaction-artifact/0.1"
    artifact_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_run_id: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    source_head_revision: int = Field(ge=0)
    baseline_run: PersonaReactionBaselineRun
    model_run: PersonaReactionModelRun
    prediction_freeze: PersonaReactionPredictionFreeze
    target_set: PersonaReactionTargetSet
    result: PersonaReactionComparisonResult
    private_local_only: Literal[True] = True
    raw_target_text_persisted: Literal[False] = False
    calibrated: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    authority: Literal["none"] = "none"
    action_status: Literal["not_performed"] = "not_performed"
    artifact_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def artifact_is_canonical(self) -> PersonaReactionBenchmarkArtifact:
        freeze = self.prediction_freeze
        target = self.target_set
        result = self.result
        expected_id = canonical_sha256(
            {
                "source_run_id": self.source_run_id,
                "source_head_sha256": self.source_head_sha256,
                "prediction_freeze_sha256": freeze.freeze_sha256,
                "target_set_sha256": target.target_set_sha256,
                "result_sha256": result.result_sha256,
            }
        )
        if self.artifact_id != expected_id:
            raise ValueError("reaction artifact identifier is invalid")
        if not _chain_matches(self):
            raise ValueError("reaction artifact receipt chain is inconsistent")
        payload = self.model_dump(mode="json", exclude={"artifact_sha256"})
        if self.artifact_sha256 != canonical_sha256(payload):
            raise ValueError("reaction artifact hash does not match")
        return self


def _chain_matches(artifact: PersonaReactionBenchmarkArtifact) -> bool:
    freeze = artifact.prediction_freeze
    target = artifact.target_set
    result = artifact.result
    return bool(
        artifact.baseline_run.manifest_sha256
        == artifact.model_run.manifest_sha256
        == freeze.manifest_sha256
        == target.manifest_sha256
        == result.manifest_sha256
        and freeze.upstream_run_sha256s
        == (artifact.baseline_run.run_sha256, artifact.model_run.run_sha256)
        and target.prediction_freeze_sha256 == freeze.freeze_sha256
        and result.prediction_freeze_sha256 == freeze.freeze_sha256
        and result.target_set_sha256 == target.target_set_sha256
        and target.source_manifest_sha256 == artifact.source_manifest_sha256
        and target.source_head_sha256 == artifact.source_head_sha256
        and target.source_head_revision == artifact.source_head_revision
        and not freeze.synthetic
        and not target.synthetic
    )
