# ruff: noqa: RUF001 -- Turkish user-facing copy is intentional.

from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.errors import PolicyViolation
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_attempts import ProposalAttempt
from ynoy.persona_study.assisted_labels import propose_assisted_labels
from ynoy.persona_study.local_proposer import LocalPersonaProposer


def propose_labels(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    settings = context.settings
    proposer = _configured_proposer(context)
    store = PersonaStudyStore(settings.require_private_root(), real_data=not bool(args.synthetic))
    attempt: ProposalAttempt = "retry_01" if args.retry_unreliable else "primary"
    result = propose_assisted_labels(store, args.study_id, proposer, attempt=attempt)
    receipt = result.bundle.receipt
    ready = receipt.status == "review_ready"
    return {
        "status": "awaiting_quick_proposal_review" if ready else "proposal_run_unreliable",
        "attempt": attempt,
        "message_tr": (
            "Yerel model önerileri iki geçiş ve deterministik kapılardan geçti."
            if ready
            else "Model geçişleri denetim yükü sınırını aştığı için güvenilmez sayıldı."
        ),
        "next_step_tr": (
            "Seçilen küçük denetim grubunda Doğru, Düzelt veya Bana ait değil kararı ver."
            if ready
            else "Bu önerileri persona için kullanma; model veya protokol karşılaştırması yap."
        ),
        "counts": {
            "presentations": receipt.presentation_count,
            "stable": receipt.stable_count,
            "disagreements": receipt.disagreement_count,
            "blind_repeat_disagreements": receipt.blind_repeat_disagreement_count,
            "deterministic_guard_passes": receipt.deterministic_guard_pass_count,
            "invalid_passes": receipt.invalid_pass_count,
            "required_reviews": receipt.required_review_count,
            "review_burden_cap": receipt.review_burden_cap,
        },
        "review_available": result.quick_review_path is not None,
        "model_provider_used": receipt.model_provider_used,
        "represented_user_labels_used": receipt.represented_user_labels_used,
        "persona_quality_claimed": receipt.persona_quality_claimed,
        "protected_holdout_used": receipt.protected_holdout_used,
        "automatic_core_promotion": receipt.automatic_core_promotion,
        "private_content_emitted": False,
    }


def _configured_proposer(context: CommandContext) -> LocalPersonaProposer:
    settings = context.settings
    if not (
        settings.local_reasoner_url
        and settings.local_reasoner_model_explicit
        and settings.local_reasoner_revision
        and settings.local_reasoner_artifact_sha256
    ):
        raise PolicyViolation(
            "persona_proposer_not_configured",
            "Explicitly configure the pinned local model, endpoint, revision, "
            "and artifact SHA-256.",
        )
    return LocalPersonaProposer(
        endpoint=settings.local_reasoner_url,
        model=settings.local_reasoner_model,
        revision=settings.local_reasoner_revision,
        artifact_sha256=settings.local_reasoner_artifact_sha256,
        local_attested=settings.local_model_attested,
    )
