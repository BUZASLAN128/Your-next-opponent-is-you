# ruff: noqa: RUF001 -- Turkish user-facing copy is intentional.

from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.errors import DataValidationError
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_review_submission import (
    record_proposal_review_decisions,
    submit_proposal_review,
)


def record_proposal_review(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    result = record_proposal_review_decisions(
        _store(args, context),
        args.study_id,
        confirm_orders=_orders(args.confirm),
        not_mine_orders=_orders(args.not_mine),
        correct_orders=_orders(args.correct),
    )
    ready = result.pending_count == 0
    return {
        "status": (
            "proposal_review_ready_to_submit" if ready else "awaiting_quick_proposal_review"
        ),
        "attempt": result.attempt,
        "message_tr": (
            "Kısa öneri denetimindeki tüm kararlar kaydedildi."
            if ready
            else "Kısa öneri denetimi kısmen kaydedildi."
        ),
        "next_step_tr": (
            "Kararları değişmez makbuza dönüştürmek için submit-proposal-review çalıştır."
            if ready
            else "Kalan kartları veya düzeltme ayrıntılarını tamamla."
        ),
        "counts": {
            "selected": result.selected_count,
            "decided": result.decided_count,
            "pending": result.pending_count,
            "correction_details_pending": result.correction_pending_count,
        },
        "private_content_emitted": False,
        "persona_quality_claimed": False,
        "automatic_core_promotion": False,
    }


def submit_recorded_proposal_review(
    args: argparse.Namespace, context: CommandContext
) -> dict[str, object]:
    result = submit_proposal_review(_store(args, context), args.study_id)
    receipt = result.receipt
    return {
        "status": "proposal_review_sealed_not_persona_quality",
        "attempt": result.attempt,
        "message_tr": "Temsil edilen kullanıcının kısa öneri denetimi mühürlendi.",
        "next_step_tr": (
            "Bu yalnız model önerisi denetimidir; persona kalitesi için bağımsız etiket ve "
            "saklı değerlendirme gerekir."
        ),
        "counts": {
            "reviewed": receipt.reviewed_count,
            "confirmed": receipt.confirm_count,
            "corrected": receipt.correct_count,
            "not_mine": receipt.not_mine_count,
            "proposal_available": receipt.proposal_available_count,
        },
        "model_provider_used": receipt.model_provider_used,
        "represented_user_review_used": receipt.represented_user_review_used,
        "persona_quality_claimed": receipt.persona_quality_claimed,
        "protected_holdout_used": receipt.protected_holdout_used,
        "automatic_core_promotion": receipt.automatic_core_promotion,
        "private_content_emitted": False,
    }


def _orders(raw: str | None) -> tuple[int, ...]:
    if raw is None:
        return ()
    parts = tuple(item.strip() for item in raw.split(","))
    try:
        values = tuple(int(item) for item in parts if item)
    except ValueError as exc:
        raise DataValidationError(
            "persona_proposal_review_order_invalid", "Review card orders must be integers."
        ) from exc
    invalid = not parts or any(not item for item in parts)
    if invalid or any(value < 1 or value > 32 for value in values):
        raise DataValidationError(
            "persona_proposal_review_order_invalid", "Review card orders must be between 1 and 32."
        )
    return values


def _store(args: argparse.Namespace, context: CommandContext) -> PersonaStudyStore:
    return PersonaStudyStore(
        context.settings.require_private_root(), real_data=not bool(args.synthetic)
    )
