# ruff: noqa: RUF001 -- Turkish deterministic safety response is intentional.

from __future__ import annotations

from ynoy.full_persona.response_protocol import PersonaResponseCandidate
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
