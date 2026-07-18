# ruff: noqa: RUF001 -- Turkish dotless-i text is intentional user-facing copy.

from __future__ import annotations

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
    "proposal_review_sealed_not_persona_quality": (
        "Temsil edilen kullanıcının kısa öneri denetimi mühürlendi.",
        "Bu model denetimidir; persona kalitesi için bağımsız etiket ve saklı ölçüm gerekir.",
    ),
}


def status_guidance_tr(status: str) -> tuple[str, str]:
    try:
        return _STATUS_GUIDANCE_TR[status]
    except KeyError as exc:
        raise ValueError(f"unsupported persona-study status: {status}") from exc
