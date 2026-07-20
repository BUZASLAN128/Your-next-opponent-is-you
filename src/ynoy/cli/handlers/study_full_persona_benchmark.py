from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.errors import PolicyViolation
from ynoy.full_persona.reaction_artifact import build_reaction_artifact
from ynoy.full_persona.reaction_artifact_store import FullPersonaReactionStore
from ynoy.full_persona.reaction_model import LocalReactionModelAdapter
from ynoy.full_persona.reaction_verified import run_verified_reaction_benchmark
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.persona_reaction_benchmark import REACTION_ARMS
from ynoy.models.persona_reaction_results import PersonaReactionComparisonResult


def benchmark_full_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    root = context.settings.require_private_root()
    store = FullPersonaStore(root, synthetic=False)
    manifest = store.read_manifest(args.run_id)
    head = store.read_head(args.run_id)
    benchmark = run_verified_reaction_benchmark(_configured_adapter(context), store, manifest, head)
    artifact = build_reaction_artifact(manifest, head, benchmark)
    FullPersonaReactionStore(root).write(artifact)
    return _safe_summary(benchmark.result)


def _configured_adapter(context: CommandContext) -> LocalReactionModelAdapter:
    settings = context.settings
    if not (
        settings.local_reasoner_url
        and settings.local_reasoner_model_explicit
        and settings.local_reasoner_revision
        and settings.local_reasoner_artifact_sha256
        and settings.local_reasoner_artifact_path
    ):
        raise PolicyViolation(
            "persona_benchmark_not_configured",
            "Configure the pinned loopback model, revision, artifact file, and SHA-256.",
        )
    return LocalReactionModelAdapter(
        endpoint=settings.local_reasoner_url,
        model=settings.local_reasoner_model,
        revision=settings.local_reasoner_revision,
        artifact_sha256=settings.local_reasoner_artifact_sha256,
        artifact_path=settings.local_reasoner_artifact_path,
        local_attested=settings.local_model_attested,
    )


def _safe_summary(result: PersonaReactionComparisonResult) -> dict[str, object]:
    return {
        "status": result.status,
        "reason": result.reason,
        "case_count": result.case_count,
        "cluster_count": result.cluster_count,
        "arms": {
            arm: {
                "correct": result.correct[arm],
                "wrong": result.wrong[arm],
                "abstained": result.abstained[arm],
                "coverage": result.coverage[arm],
                "risk": result.risk[arm],
                "matched_risk": result.matched_risk[arm],
            }
            for arm in REACTION_ARMS
        },
        "calibrated": False,
        "persona_quality_claimed": False,
        "authority": "none",
        "action_status": "not_performed",
        "private_content_emitted": False,
        "private_path_emitted": False,
    }
