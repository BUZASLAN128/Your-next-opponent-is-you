# ruff: noqa: RUF001 -- Turkish user-facing copy is intentional.

from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest_authorship import (
    current_all_self_submission,
    submit_harvest_authorship,
)


def seal_harvest_authorship(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    """Seal exact represented-user authorship without semantic adoption."""
    store = PersonaStudyStore(
        context.settings.require_private_root(), real_data=not bool(args.synthetic)
    )
    submission = current_all_self_submission(
        store,
        args.run_id,
        expected_revision=args.revision,
        expected_checkpoint_sha256=args.checkpoint_sha256,
    )
    result = submit_harvest_authorship(store, submission)
    receipt = result.receipt
    return {
        "status": "harvest_authorship_sealed_not_judgment",
        "message_tr": "İncelenen kayıtların sana ait olduğu özel alanda mühürlendi.",
        "next_step_tr": (
            "Karar anlamı, güncel benimseme ve persona uygunluğu ayrı inceleme ister."
        ),
        "revision": receipt.revision,
        "confirmed_authorship_count": len(receipt.candidate_ids),
        "authenticator_verified": receipt.authenticator_verified,
        "judgment_signal": receipt.judgment_signal,
        "adoption": receipt.adoption,
        "core_eligible": receipt.core_eligible,
        "benchmark_eligible": receipt.benchmark_eligible,
        "decision_atoms_projected": receipt.decision_atoms_projected,
        "private_content_emitted": False,
        "database_used": receipt.database_used,
        "model_provider_used": receipt.model_provider_used,
        "automatic_core_promotion": receipt.automatic_core_promotion,
        "persona_quality_claimed": receipt.persona_quality_claimed,
    }
