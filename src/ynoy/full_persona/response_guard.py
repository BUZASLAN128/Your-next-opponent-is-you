# ruff: noqa: RUF001 -- Turkish deterministic safety response is intentional.

from __future__ import annotations

from ynoy.full_persona.identity_rules import is_biography_query, life_facts
from ynoy.full_persona.response_context import PersonaContextEntry
from ynoy.full_persona.response_protocol import PersonaResponseCandidate
from ynoy.models.full_persona_pack import PersonaLayer
from ynoy.models.persona_response import PersonaResponseArm


def public_uncertainties(arm: PersonaResponseArm) -> tuple[str, ...]:
    if arm == "generic":
        return (
            "Bu kontrol koluna kişisel kanıt verilmedi.",
            "Çıktı kalibre edilmemiştir.",
        )
    return (
        "Persona benzerliği henüz kalibre edilmedi.",
        "Seçilen gözlemler benimsenmiş kimlik doğruları değildir.",
    )


def runtime_guard_candidate(query: str, arm: PersonaResponseArm) -> PersonaResponseCandidate | None:
    normalized = query.casefold()
    corpus_terms = ("gb", "gib", "veri", "corpus", "konuşma")
    memory_terms = ("ram", "bellek")
    residency_terms = ("yükle", "sığ", "tut")
    if not (
        any(term in normalized for term in corpus_terms)
        and any(term in normalized for term in memory_terms)
        and any(term in normalized for term in residency_terms)
    ):
        return None
    prefix = "Yok" if arm == "structured" else "Hayır"
    text = (
        f"{prefix}, corpusun tamamını RAM'e yüklemek gerekmiyor. Veri diskten akışla "
        "işlenir; modele yalnız sorguyla ilgili küçük kanıt paketi girer. Burada ölçmemiz "
        "gereken şey RAM değil, retrieval ve persona kalitesi."
    )
    return PersonaResponseCandidate(
        response_text=text,
        used_atom_ids=(),
        uncertainties=("Bu yanıt doğrulanmış çalışma zamanı invariantına dayanır.",),
        should_abstain=True,
    )


def biography_evidence_candidate(
    query: str,
    arm: PersonaResponseArm,
    context: tuple[PersonaContextEntry, ...],
) -> PersonaResponseCandidate | None:
    if arm != "structured" or not is_biography_query(query):
        return None
    facts: list[str] = []
    used_ids: list[str] = []
    observed_topics: set[str] = set()
    for item in context:
        if item.layer != PersonaLayer.AUTOBIOGRAPHY:
            continue
        extracted = life_facts(item.claim)
        if not extracted:
            continue
        used_ids.append(item.atom_id)
        for topic, fact in extracted:
            observed_topics.add(topic)
            if fact not in facts:
                facts.append(fact)
    unknown = [
        label
        for topic, label in (
            ("birth", "doğum"),
            ("childhood", "çocukluk"),
            ("education", "eğitim"),
            ("exams", "sınav geçmişi"),
        )
        if topic not in observed_topics
    ]
    if facts:
        text = f'Geçmiş kaydında "{"; ".join(facts)}" diye yazmışsın. '
    else:
        text = "Geçmiş kaydında doğrulanabilir bir yaşam ayrıntısı bulamadım. "
    if unknown:
        text += f"{', '.join(unknown)} için literal kanıt yok; kalanını uyduramam."
    return PersonaResponseCandidate(
        response_text=text,
        used_atom_ids=tuple(sorted(set(used_ids))),
        uncertainties=("Tarihsel ifadeler güncel kimlik doğrusu olarak benimsenmemiştir.",),
        should_abstain=True,
    )
