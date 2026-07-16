# ruff: noqa: RUF001 -- Turkish dotless-i text is intentional user-facing copy.

from __future__ import annotations

from typing import Literal

from ynoy.models import AnnotationPresentation

LabelSchemaVersion = Literal["persona-labels/0.1", "persona-labels/0.2"]

_LABEL_INSTRUCTIONS_V01 = (
    "Her null alani yalniz kendi yarginla doldur.",
    "Yapisal user rolu, sozlerin sana ait oldugunu kanitlamaz.",
    "Kart tanidik gelse bile onceki yaniti kopyalama.",
    "Exact span alanlarinda focus metnindeki karakter araliklarini kullan.",
    "Ilk submit-labels islemi cevaplarini immutable yapar; once yerel kopyani kontrol et.",
    "Blind-repeat uyusmazligi olursa ilk cevaplar korunur ve ayri adjudication acilir.",
    "Bitirdiginde completed_by alanini represented_user yap.",
)

_LABEL_INSTRUCTIONS = (
    "Zorunlu karar alanlarını yalnız kendi yargına göre doldur; koşullu ve isteğe "
    "bağlı alanları aşağıdaki kurallara göre `null` bırak.",
    "Yapısal `user` rolü, sözlerin sana ait olduğunu kanıtlamaz.",
    "Kart tanıdık gelse bile önceki yanıtını kopyalama; bağımsız değerlendir.",
    "`rationale_spans` ve `evidence_demand_spans` için hedef metindeki tam karakter "
    "aralıklarını kullan.",
    "İlk `submit-labels` işlemi yanıtlarını değiştirilemez olarak mühürler; "
    "göndermeden önce yerel kopyanı kontrol et.",
    "Kör tekrarlarda uyuşmazlık çıkarsa ilk yanıtlar korunur ve ayrı bir uzlaştırma formu açılır.",
    "Tüm etiketleri bitirdiğinde `completed_by` alanını `represented_user` yap.",
)

_ALLOWED_VALUES = {
    "authorship": ("self", "quoted_or_pasted", "mixed", "other", "unknown"),
    "claim_holder": ("self", "assistant", "third_party", "mixed", "unknown"),
    "adoption": ("endorsed", "rejected", "hypothetical", "not_applicable", "unknown"),
    "decision": ("accept", "reject", "correct", "defer", "ask", "none", "unknown"),
    "target_layer": (
        "persona",
        "project_rule",
        "architecture",
        "mission",
        "episodic",
        "research",
        "none",
        "unknown",
    ),
    "confidence": ("high", "medium", "low", "unknown"),
    "persona_kind": (
        "trait",
        "value",
        "narrative",
        "metacognition",
        "belief",
        "preference",
        "goal",
        "relationship",
        "skill",
    ),
    "scope_risk": ("low", "medium", "high", "unknown"),
}

_VALUE_GUIDE = (
    "## Sabit alanlar için Türkçe sözlük",
    "",
    "Alan adlarını ve aşağıdaki sabit değerleri çevirmeden kullan:",
    "",
    "- `authorship`: `self` bana ait; `quoted_or_pasted` alıntı veya yapıştırma; "
    "`mixed` karışık; `other` başkasına ait; `unknown` bilinmiyor.",
    "- `claim_holder`: iddiayı taşıyan kişi; `self`, `assistant`, `third_party`, "
    "`mixed` veya `unknown`.",
    "- `adoption`: `endorsed` hâlen benimsiyorum; `rejected` reddediyorum; "
    "`hypothetical` varsayım; `not_applicable` uygulanamaz; `unknown` bilinmiyor.",
    "- `decision`: `accept` kabul; `reject` ret; `correct` düzeltme; `defer` erteleme; "
    "`ask` soru; `none` karar yok; `unknown` bilinmiyor.",
    "- `target_layer`: `persona` kişilik; `project_rule` proje kuralı; "
    "`architecture` mimari; `mission` misyon; `episodic` olaysal hafıza; "
    "`research` araştırma; `none` katman yok; `unknown` bilinmiyor.",
    "- `persona_kind`: kişilik katmanı seçildiyse nitelik, değer, anlatı, "
    "üstbiliş, inanç, tercih, hedef, ilişki veya beceri türü.",
    "- `should_abstain`: sistemin karar vermemesi gerekiyorsa `true`.",
    "- `exclude_from_persona`: metin kişilik kanıtı olmayacaksa `true`; "
    "bu durumda `exclusion_reason` alanını da doldur.",
    "- `confidence`: `high` yüksek; `medium` orta; `low` düşük; `unknown` bilinmiyor.",
    "",
)


def label_template(
    study_id: str,
    presentations: tuple[AnnotationPresentation, ...],
    *,
    schema_version: LabelSchemaVersion = "persona-labels/0.2",
) -> dict[str, object]:
    instructions = (
        _LABEL_INSTRUCTIONS_V01 if schema_version == "persona-labels/0.1" else _LABEL_INSTRUCTIONS
    )
    return {
        "schema_version": schema_version,
        "study_id": study_id,
        "completed_by": None,
        "instructions": list(instructions),
        "allowed_values": {key: list(values) for key, values in _ALLOWED_VALUES.items()},
        "labels": [_empty_label(item.presentation_id) for item in presentations],
    }


def render_review_markdown(presentations: tuple[AnnotationPresentation, ...]) -> str:
    lines = [
        "# Özel Kişilik Etiketleme Paketi",
        "",
        "Bu etiketleme paketi Git dışında ve özel kalır; model önerisi içermez.",
        "Değerlendirici eşleme kayıtları ayrı bir özel kökte tutulur. Bu ayrım "
        "kriptografik koruma değildir.",
        "Her kartı bağımsız değerlendir. `user` rolü yalnız yapısal bir gözlemdir.",
        "Aynı klasördeki `labels.template.json` dosyasında zorunlu karar alanlarını doldur. "
        "Koşullu veya isteğe bağlı alanlar uygulanmıyorsa `null` bırak.",
        "Dosya adını, kart kimliğini ve kanıt metnini değiştirme.",
        "`authorship=self` değerini yalnız söz gerçekten sana aitse kullan.",
        "`adoption=endorsed` değerini söz bugün de geçerliyse kullan.",
        "Emin değilsen `unknown` ve `should_abstain=true` seç.",
        "`submit-labels` ilk yanıtları değiştirilemez olarak mühürler. Kör tekrarlar "
        "uyuşmazsa ayrı bir uzlaştırma formu açılır.",
        "",
    ]
    lines.extend(_VALUE_GUIDE)
    for presentation in presentations:
        lines.extend(_card(presentation))
    return "\n".join(lines).rstrip() + "\n"


def _empty_label(presentation_id: str) -> dict[str, object]:
    return {
        "presentation_id": presentation_id,
        "authorship": None,
        "claim_holder": None,
        "adoption": None,
        "decision": None,
        "target_layer": None,
        "persona_kind": None,
        "scope": {
            "project": None,
            "role": None,
            "audience": None,
            "risk": "unknown",
            "temporal": None,
        },
        "rationale_spans": [],
        "evidence_demand_spans": [],
        "should_abstain": None,
        "exclude_from_persona": None,
        "exclusion_reason": None,
        "confidence": None,
        "notes": None,
    }


def _card(presentation: AnnotationPresentation) -> list[str]:
    lines = [
        f"## Kart {presentation.order:02d}",
        "",
        f"Kart kimliği: `{presentation.presentation_id}`",
        "",
        "### Önceki bağlam",
        "",
    ]
    for message in presentation.context:
        lines.append(f"Yapısal konuşmacı: `{message.speaker.value}`")
        lines.extend(("", *_indented(message.content), ""))
    lines.extend(("### Hedef ileti", "", "Yapısal konuşmacı: `user`", ""))
    lines.extend(_indented(presentation.focus.content))
    lines.extend(("", "Karşılık gelen JSON etiketini bağımsız olarak doldur.", ""))
    return lines


def _indented(text: str) -> list[str]:
    return [f"    {line}" for line in text.splitlines() or [""]]
