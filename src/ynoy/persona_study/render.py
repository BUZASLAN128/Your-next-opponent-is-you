from __future__ import annotations

from ynoy.models import AnnotationPresentation


def label_template(
    study_id: str, presentations: tuple[AnnotationPresentation, ...]
) -> dict[str, object]:
    return {
        "schema_version": "persona-labels/0.1",
        "study_id": study_id,
        "completed_by": None,
        "instructions": [
            "Her null alani yalniz kendi yarginla doldur.",
            "Yapisal user rolu, sozlerin sana ait oldugunu kanitlamaz.",
            "Kart tanidik gelse bile onceki yaniti kopyalama.",
            "Exact span alanlarinda focus metnindeki karakter araliklarini kullan.",
            "Ilk submit-labels islemi cevaplarini immutable yapar; once yerel kopyani kontrol et.",
            "Blind-repeat uyusmazligi olursa ilk cevaplar korunur ve ayri adjudication acilir.",
            "Bitirdiginde completed_by alanini represented_user yap.",
        ],
        "allowed_values": {
            "authorship": ["self", "quoted_or_pasted", "mixed", "other", "unknown"],
            "claim_holder": ["self", "assistant", "third_party", "mixed", "unknown"],
            "adoption": ["endorsed", "rejected", "hypothetical", "not_applicable", "unknown"],
            "decision": ["accept", "reject", "correct", "defer", "ask", "none", "unknown"],
            "target_layer": [
                "persona",
                "project_rule",
                "architecture",
                "mission",
                "episodic",
                "research",
                "none",
                "unknown",
            ],
            "confidence": ["high", "medium", "low", "unknown"],
            "persona_kind": [
                "trait",
                "value",
                "narrative",
                "metacognition",
                "belief",
                "preference",
                "goal",
                "relationship",
                "skill",
            ],
            "scope_risk": ["low", "medium", "high", "unknown"],
        },
        "labels": [_empty_label(item.presentation_id) for item in presentations],
    }


def render_review_markdown(presentations: tuple[AnnotationPresentation, ...]) -> str:
    lines = [
        "# Ozel Persona Etiketleme Paketi",
        "",
        "Bu annotator paketi Git disinda ve ozel kalir; model onerisi icermez.",
        "Evaluator esleme kayitlari ayri bir ozel kokte tutulur; bu kriptografik koruma degildir.",
        "Her karti bagimsiz degerlendir. `user` rolu yalniz yapisal bir gozlemdir.",
        "Ayni klasorde `labels.template.json` icindeki null alanlari yerinde doldur.",
        "Dosya adini ve kanit metnini degistirme.",
        "`authorship=self` yalniz soz gercekten seninse kullanilir.",
        "`adoption=endorsed` sozun bugun de gecerliyse kullanilir.",
        "Emin degilsen `unknown` ve `should_abstain=true` sec.",
        "`submit-labels` ilk cevaplari immutable saklar; uyusmazlik varsa ayri adjudication ister.",
        "",
    ]
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
        f"Presentation ID: `{presentation.presentation_id}`",
        "",
        "### Onceki baglam",
        "",
    ]
    for message in presentation.context:
        lines.append(f"Yapisal konusmaci: `{message.speaker.value}`")
        lines.extend(("", *_indented(message.content), ""))
    lines.extend(("### Hedef donus", "", "Yapisal konusmaci: `user`", ""))
    lines.extend(_indented(presentation.focus.content))
    lines.extend(("", "Eslesen JSON etiketini bagimsiz doldur.", ""))
    return lines


def _indented(text: str) -> list[str]:
    return [f"    {line}" for line in text.splitlines() or [""]]
