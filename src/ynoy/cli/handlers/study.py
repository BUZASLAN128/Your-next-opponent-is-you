# ruff: noqa: RUF001 -- Turkish dotless-i text is intentional user-facing copy.

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.study_proposals import propose_labels
from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactIndex
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_attempts import RETRY_PROPOSALS_PATH
from ynoy.persona_study.assisted_labels import (
    PROPOSALS_PATH,
    QUICK_REVIEW_PATH,
)
from ynoy.persona_study.assisted_review import RETRY_QUICK_REVIEW_PATH
from ynoy.persona_study.label_submission import submit_persona_labels
from ynoy.persona_study.labels import seal_persona_labels
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.policy import assert_outside_git
from ynoy.util import utc_now

_STATUS_GUIDANCE_TR = {
    "awaiting_represented_user_labels": (
        "Paket hazır; temsil edilen kullanıcının 32 kör etiketi tamamlaması bekleniyor.",
        "Önce inceleme kartlarını oku, sonra etiket dosyasındaki boş alanları doldur.",
    ),
    "initial_submission_sealed": (
        "İlk etiket gönderimi değiştirilemez olarak mühürlendi.",
        "Çalışma durumunu yeniden denetle; gerekiyorsa uzlaştırma formunu tamamla.",
    ),
    "awaiting_repeat_adjudication": (
        "Kör tekrar uyuşmazlıkları için kullanıcı uzlaştırması bekleniyor.",
        "Uzlaştırma formundaki nihai yargıları doldur, sonra etiketleri mühürle.",
    ),
    "annotation_initial_submission_sealed_awaiting_adjudication": (
        "İlk yanıtlar mühürlendi; kör tekrar uyuşmazlıkları ayrı biçimde korunuyor.",
        "Oluşturulan uzlaştırma formunu tamamladıktan sonra `seal-labels` çalıştır.",
    ),
    "annotation_labels_sealed_not_persona_quality": (
        "Etiketler mühürlendi; bu sonuç henüz kişilik benzerliği kalitesi kanıtı değildir.",
        "Saklı değerlendirme adımı, ayrı bütünlük kontrollerinden sonra açılabilir.",
    ),
    "expired_artifacts_purged": (
        "Süresi dolan özel çalışma kalıntıları temizlendi.",
        "Gerekirse çalışma durumunu yeniden denetle.",
    ),
    "expiry_purge_incomplete": (
        "Süresi dolan bazı özel çalışma kalıntıları güvenli biçimde temizlenemedi.",
        "Yeni işleme geçmeden önce başarısız temizleme kayıtlarını incele.",
    ),
    "derived_study_deleted": (
        "Türetilmiş çalışma ve kayıtlı bağımlılık kapanımı silindi.",
        "Kaynak konuşmalar değiştirilmedi; gerekiyorsa yeni bir çalışma hazırla.",
    ),
    "awaiting_quick_proposal_review": (
        "Yerel model önerileri iki geçiş ve deterministik kapılardan geçti.",
        "Seçilen küçük denetim grubunda Doğru, Düzelt veya Bana ait değil kararı ver.",
    ),
    "proposal_run_unreliable": (
        "Model geçişleri denetim yükü sınırını aştığı için güvenilmez sayıldı.",
        "Bu önerileri persona için kullanma; model veya protokol karşılaştırması yap.",
    ),
}


def handle_study(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    handlers = {
        "prepare": _prepare,
        "status": _status,
        "purge-expired": _purge_expired,
        "delete": _delete,
        "submit-labels": _submit_labels,
        "seal-labels": _seal_labels,
        "propose-labels": propose_labels,
    }
    return handlers[args.study_command](args, context)


def _prepare(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source = Path(args.codex_root)
    if not synthetic:
        assert_outside_git(source)
    result = prepare_persona_study(
        source,
        context.settings.require_private_root(),
        synthetic=synthetic,
    )
    manifest = result.manifest
    message_tr, next_step_tr = _status_guidance_tr(manifest.status)
    return {
        "status": manifest.status,
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "study_id": manifest.study_id,
        "manifest_sha256": manifest.manifest_sha256,
        "selection_sha256": manifest.selection_sha256,
        "blind_map_sha256": manifest.blind_map_sha256,
        "counts": {
            "selected_files": manifest.selected_file_count,
            "normalized_events": manifest.normalized_event_count,
            "unique_windows": manifest.unique_window_count,
            "presentations": manifest.presentation_count,
            "blind_repeats": manifest.blind_repeat_count,
            "annotation_development": manifest.annotation_development_count,
            "annotation_reserved": manifest.annotation_reserved_count,
            "dependency_components": manifest.dependency_component_count,
        },
        "review_path": str(result.review_path),
        "labels_path": str(result.labels_path),
        "expires_at": manifest.expires_at,
        "independent_source_replay_verified": manifest.independent_source_replay_verified,
        "disposable_canary_deletion_proof": "passed",
        "retention_enforcement": manifest.retention_enforcement,
        "background_deletion_guaranteed": manifest.background_deletion_guaranteed,
        "protected_holdout_claimed": manifest.protected_holdout_claimed,
        "blinding_scope": "operational_directory_separation_not_cryptographic",
        "source_deleted": False,
        "raw_content_emitted": False,
        "database_used": False,
        "model_provider_used": False,
        "automatic_core_promotion": False,
        "expired_artifacts_purged": result.expired_artifacts_purged,
        "expired_tombstones_purged": result.expired_tombstones_purged,
    }


def _status(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    store = _store(args, context)
    purge = store.purge_expired(utc_now())
    if purge.failed_count:
        message_tr, next_step_tr = _status_guidance_tr("expiry_purge_incomplete")
        return {
            "status": "expiry_purge_incomplete",
            "message_tr": message_tr,
            "next_step_tr": next_step_tr,
            "failed_run_count": purge.failed_run_count,
            "failed_tombstone_count": purge.failed_tombstone_count,
            "content_emitted": False,
        }
    index = store.read_index(args.study_id)
    status = _study_status(store, index)
    message_tr, next_step_tr = _status_guidance_tr(status)
    return {
        "status": status,
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "study_id": index.study_id,
        "expires_at": index.expires_at,
        "artifact_count": len(index.entries),
        "content_emitted": False,
    }


def _purge_expired(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    result = _store(args, context).purge_expired(utc_now())
    status = "expired_artifacts_purged" if not result.failed_count else "expiry_purge_incomplete"
    message_tr, next_step_tr = _status_guidance_tr(status)
    return {
        "status": status,
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "deleted_artifact_count": result.deleted_artifact_count,
        "deleted_tombstone_count": result.deleted_tombstone_count,
        "failed_run_count": result.failed_run_count,
        "failed_tombstone_count": result.failed_tombstone_count,
        "retention_enforcement": "on_access",
        "background_deletion_guaranteed": False,
    }


def _delete(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    store = _store(args, context)
    deleted = store.delete_run(args.study_id)
    store.require_absent(args.study_id)
    message_tr, next_step_tr = _status_guidance_tr("derived_study_deleted")
    return {
        "status": "derived_study_deleted",
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "deleted_artifact_count": deleted,
        "source_deleted": False,
    }


def _submit_labels(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    result = submit_persona_labels(_store(args, context), args.study_id)
    receipt = result.initial_receipt
    status = (
        "annotation_initial_submission_sealed_awaiting_adjudication"
        if receipt.adjudication_required
        else "annotation_labels_sealed_not_persona_quality"
    )
    message_tr, next_step_tr = _status_guidance_tr(status)
    return {
        "status": status,
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "blind_repeat_pairs": receipt.repeat_pair_count,
        "initial_exact_matches": receipt.repeat_exact_match_count,
        "initial_mismatches": receipt.repeat_mismatch_count,
        "adjudication_required": receipt.adjudication_required,
        "persona_quality_claimed": receipt.persona_quality_claimed,
        "protected_holdout_used": receipt.protected_holdout_used,
        "private_content_emitted": False,
    }


def _seal_labels(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    result = seal_persona_labels(_store(args, context), args.study_id)
    receipt = result.receipt
    message_tr, next_step_tr = _status_guidance_tr("annotation_labels_sealed_not_persona_quality")
    return {
        "status": "annotation_labels_sealed_not_persona_quality",
        "message_tr": message_tr,
        "next_step_tr": next_step_tr,
        "counts": {
            "presentations": receipt.presentation_count,
            "unique_windows": receipt.unique_window_count,
            "blind_repeat_pairs": receipt.repeat_pair_count,
            "initial_exact_matches": receipt.initial_repeat_exact_match_count,
            "adjudicated_pairs": receipt.adjudicated_repeat_pair_count,
            "excluded_from_persona": receipt.excluded_from_persona_count,
            "abstained": receipt.abstained_count,
            "persona_candidates": receipt.persona_candidate_count,
        },
        "persona_quality_claimed": receipt.persona_quality_claimed,
        "protected_holdout_used": receipt.protected_holdout_used,
        "model_provider_used": receipt.model_provider_used,
        "automatic_core_promotion": receipt.automatic_core_promotion,
        "private_content_emitted": False,
    }


def _store(args: argparse.Namespace, context: CommandContext) -> PersonaStudyStore:
    return PersonaStudyStore(
        context.settings.require_private_root(), real_data=not bool(args.synthetic)
    )


def _study_status(store: PersonaStudyStore, index: StudyArtifactIndex) -> str:
    paths = {item.relative_path for item in index.entries}
    if "evaluator/label-seal.json" in paths:
        return "annotation_labels_sealed_not_persona_quality"
    if "annotator/repeat-adjudication.template.json" in paths:
        return "awaiting_repeat_adjudication"
    if "evaluator/repeat-agreement.initial.json" in paths:
        return "initial_submission_sealed"
    if RETRY_PROPOSALS_PATH in paths:
        if RETRY_QUICK_REVIEW_PATH in paths:
            return "awaiting_quick_proposal_review"
        if _proposal_status(store, index.study_id, RETRY_PROPOSALS_PATH) == "unreliable":
            return "proposal_run_unreliable"
    if PROPOSALS_PATH in paths:
        if QUICK_REVIEW_PATH in paths:
            return "awaiting_quick_proposal_review"
        if _proposal_status(store, index.study_id, PROPOSALS_PATH) == "unreliable":
            return "proposal_run_unreliable"
    return "awaiting_represented_user_labels"


def _proposal_status(store: PersonaStudyStore, study_id: str, path: str) -> str:
    try:
        value = json.loads(store.read_artifact(study_id, path))
        status = value["receipt"]["status"]
        if status not in {"review_ready", "unreliable"}:
            raise ValueError
        return str(status)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "persona_proposal_receipt_invalid",
            "The immutable persona proposal receipt is invalid.",
        ) from exc


def _status_guidance_tr(status: str) -> tuple[str, str]:
    try:
        return _STATUS_GUIDANCE_TR[status]
    except KeyError as exc:
        raise ValueError(f"unsupported persona-study status: {status}") from exc
