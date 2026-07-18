# ruff: noqa: RUF001 -- Turkish user-facing copy is intentional.

from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.persona_study.harvest import PreparedHarvest, prepare_harvest, resume_harvest
from ynoy.policy import assert_outside_git

_GUIDANCE = {
    "partial": (
        "Sabit bellekli karar taraması bir özel checkpoint üretti.",
        "Aynı run kimliğiyle `resume-harvest` çalıştırarak sıradaki dilime geç.",
    ),
    "audit_ready": (
        "Yüksek sinyalli küçük kullanıcı denetim paketi hazır.",
        "İnceleme Markdown dosyasını kontrol et; bu paket henüz persona kanıtı değildir.",
    ),
    "complete": (
        "Korumalı zaman sınırından önceki uygun kaynak dilimi tamamlandı.",
        "Küçük denetim paketini incele; model veya persona terfisi yapılmadı.",
    ),
    "complete_insufficient": (
        "Uygun kaynak dilimi tamamlandı fakat denetim için yeterli aday bulunamadı.",
        "Kapıları düşürme; sinyal sözleşmesini ayrı sentetik kanıtla yeniden değerlendir.",
    ),
}


def harvest_judgments(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    result = prepare_harvest(
        _source(args),
        context.settings.require_private_root(),
        args.source_study_id,
        synthetic=bool(args.synthetic),
    )
    return _result(result)


def resume_judgment_harvest(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    result = resume_harvest(
        _source(args),
        context.settings.require_private_root(),
        args.run_id,
        synthetic=bool(args.synthetic),
    )
    return _result(result)


def _source(args: argparse.Namespace) -> Path:
    source = Path(args.codex_root)
    if not bool(args.synthetic):
        assert_outside_git(source)
    return source


def _result(result: PreparedHarvest) -> dict[str, object]:
    checkpoint = result.checkpoint
    message_tr, next_step_tr = _GUIDANCE[checkpoint.status]
    return {
        "status": f"judgment_harvest_{checkpoint.status}",
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "run_id": result.manifest.run_id,
        "revision": checkpoint.cursor.revision,
        "candidate_count": len(checkpoint.candidates),
        "audit_card_count": min(12, len(checkpoint.candidates)),
        "review_path": str(result.review_path),
        "labels_path": str(result.labels_path),
        "cursor_status": checkpoint.cursor.status,
        "limits": result.manifest.limits.model_dump(mode="json"),
        "private_content_emitted": False,
        "persona_quality_claimed": False,
        "benchmark_eligible": False,
        "database_used": False,
        "model_provider_used": False,
        "automatic_core_promotion": False,
    }
