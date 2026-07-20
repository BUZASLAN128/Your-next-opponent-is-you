from __future__ import annotations

from typing import Any, cast

from ynoy.full_persona.reaction_verified import VerifiedReactionBenchmark
from ynoy.models.full_persona import FullCorpusHead, FullCorpusManifest
from ynoy.models.persona_reaction_artifact import PersonaReactionBenchmarkArtifact
from ynoy.util import canonical_sha256


def build_reaction_artifact(
    source_manifest: FullCorpusManifest,
    source_head: FullCorpusHead,
    benchmark: VerifiedReactionBenchmark,
) -> PersonaReactionBenchmarkArtifact:
    freeze = benchmark.prediction_freeze
    targets = benchmark.target_set
    result = benchmark.result
    artifact_id = canonical_sha256(
        {
            "source_run_id": source_manifest.run_id,
            "source_head_sha256": source_head.head_sha256,
            "prediction_freeze_sha256": freeze.freeze_sha256,
            "target_set_sha256": targets.target_set_sha256,
            "result_sha256": result.result_sha256,
        }
    )
    payload: dict[str, object] = {
        "artifact_id": artifact_id,
        "source_run_id": source_manifest.run_id,
        "source_manifest_sha256": source_manifest.manifest_sha256,
        "source_head_sha256": source_head.head_sha256,
        "source_head_revision": source_head.revision,
        "baseline_run": benchmark.baseline_run,
        "model_run": benchmark.model_run,
        "prediction_freeze": freeze,
        "target_set": targets,
        "result": result,
    }
    draft = cast(Any, PersonaReactionBenchmarkArtifact).model_construct(
        **payload, artifact_sha256="0" * 64
    )
    canonical = draft.model_dump(mode="json", exclude={"artifact_sha256"})
    return PersonaReactionBenchmarkArtifact.model_validate(
        {**canonical, "artifact_sha256": canonical_sha256(canonical)}
    )
