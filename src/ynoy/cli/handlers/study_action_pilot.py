# ruff: noqa: RUF001 -- Turkish user-facing copy is intentional.

from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.errors import PolicyViolation
from ynoy.persona_study.action_pilot_run import run_private_action_pilot
from ynoy.persona_study.action_predictor import LocalActionPredictor
from ynoy.persona_study.artifacts import PersonaStudyStore


def run_action_pilot(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    predictor = _configured_predictor(context)
    store = PersonaStudyStore(
        context.settings.require_private_root(), real_data=not bool(args.synthetic)
    )
    result = run_private_action_pilot(store, args.run_id, predictor)
    run = result.run
    return {
        "status": run.status,
        "message_tr": "Kör eylem tahmini tamamlandı ve özel depoda mühürlendi.",
        "reason": run.reason,
        "generic_correct": run.generic.correct_count,
        "personalized_correct": run.personalized.correct_count,
        "sealed_case_count": run.generic.case_count,
        "result_relative_path": result.result_relative_path,
        "observable_action_only": run.observable_action_only,
        "calibrated": run.calibrated,
        "persona_quality_claimed": run.persona_quality_claimed,
        "private_content_emitted": False,
        "automatic_core_promotion": run.automatic_core_promotion,
    }


def _configured_predictor(context: CommandContext) -> LocalActionPredictor:
    settings = context.settings
    if not (
        settings.local_reasoner_url
        and settings.local_reasoner_model_explicit
        and settings.local_reasoner_revision
        and settings.local_reasoner_artifact_sha256
    ):
        raise PolicyViolation(
            "action_predictor_not_configured",
            "Configure the pinned loopback model, revision, and artifact SHA-256.",
        )
    return LocalActionPredictor(
        endpoint=settings.local_reasoner_url,
        model=settings.local_reasoner_model,
        revision=settings.local_reasoner_revision,
        artifact_sha256=settings.local_reasoner_artifact_sha256,
        local_attested=settings.local_model_attested,
    )
