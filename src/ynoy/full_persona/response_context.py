# ruff: noqa: RUF001 -- Turkish tokenization is intentional.

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import Field

from ynoy.models.base import StrictModel
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaAtomStatus,
    PersonaLayer,
    PersonaPack,
)

_TOKEN = re.compile(r"[\wçğıöşü]+", re.I)
_MAX_CLAIM_CHARS = 600
_MAX_CONTEXT_CHARS = 3_500
_MAX_RECEIPTS_PER_ATOM = 4
_MAX_RESPONSE_CONTEXT_ATOMS = 6
_QUERY_STOPWORDS = {
    "about",
    "answer",
    "bana",
    "bir",
    "bu",
    "bundan",
    "cevap",
    "da",
    "de",
    "doğal",
    "et",
    "göre",
    "için",
    "ile",
    "ilerle",
    "ilerlemeliyiz",
    "kısa",
    "nasıl",
    "net",
    "olarak",
    "proje",
    "projede",
    "sonra",
    "şu",
    "should",
    "the",
    "ver",
    "ve",
    "what",
}
_ANCHOR_LAYERS = (
    PersonaLayer.RESPONSE_POLICY,
    PersonaLayer.VALUES,
    PersonaLayer.GOALS,
    PersonaLayer.DECISIONS,
    PersonaLayer.RISK,
    PersonaLayer.AUTOBIOGRAPHY,
    PersonaLayer.KNOWLEDGE,
    PersonaLayer.SKILLS,
    PersonaLayer.RELATIONSHIPS,
    PersonaLayer.CONTRADICTIONS,
)
_LAYER_WEIGHT = {layer: len(_ANCHOR_LAYERS) - index for index, layer in enumerate(_ANCHOR_LAYERS)}
_STYLE_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "evidence_first",
        re.compile(r"\b(kanıt|test|doğrula|incele|araştır|review)\w*\b", re.I),
        "Sonuçtan önce somut kanıt, test ve doğrulama bekler.",
    ),
    (
        "autonomous_momentum",
        re.compile(r"sana bırakıyorum|devam et|yap bakalım|kararları sen|ilerleyelim", re.I),
        "Alan netse asistanın işi kesmeden ilerletmesini tercih eder.",
    ),
    (
        "direct_conversational_turkish",
        re.compile(r"\b(bence|aynen|tamam|peki|hadi|bakalım|neyse)\b|:D", re.I),
        "Hükümle başlar; gündelik Türkçe kullanır ve gereksiz kurumsal tondan kaçınır.",
    ),
    (
        "bounded_resources",
        re.compile(r"\b(ram|bellek|çökert|çöküyor|düşük ram)\w*\b", re.I),
        "RAM ve işlem yükünü sınırlı tutmayı açık bir gereksinim sayar.",
    ),
    (
        "visible_checkpoints",
        re.compile(r"\b(push|commit|checkpoint|pr)\w*\b", re.I),
        "Anlamlı yeşil checkpointlerde görünür ilerleme ve push ister.",
    ),
    (
        "anti_hallucination",
        re.compile(r"hayal gör|halüsin|okumadığı|uydur|kanıtsız", re.I),
        "Okunmamış veya kanıtsız şeyi olmuş gibi anlatmaya düşük tolerans gösterir.",
    ),
)


class PersonaContextEntry(StrictModel):
    atom_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    layer: PersonaLayer
    claim: str = Field(min_length=1, max_length=_MAX_CLAIM_CHARS)
    truth_status: Literal["observed", "observed_unadopted", "conflicted_observation"]
    evidence_receipts: tuple[str, ...] = Field(max_length=_MAX_RECEIPTS_PER_ATOM)
    evidence_receipt_count: int = Field(ge=1)
    source_role: Literal["direct_user_expression"] = "direct_user_expression"
    adopted: Literal[False] = False
    authority: Literal["none"] = "none"


class PersonaStyleSupport(StrictModel):
    atom_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_receipts: tuple[str, ...] = Field(min_length=1, max_length=1)


class PersonaStyleSignal(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    guidance: str = Field(min_length=1, max_length=256)
    status: Literal["derived_unadopted"] = "derived_unadopted"
    supports: tuple[PersonaStyleSupport, ...] = Field(min_length=2, max_length=2)
    authority: Literal["none"] = "none"


def select_response_context(pack: PersonaPack, query: str) -> tuple[PersonaContextEntry, ...]:
    """Select a small, diverse evidence packet without converting observations to truth."""
    tokens = _tokens(query)
    limit = min(pack.config.max_retrieval_hits, _MAX_RESPONSE_CONTEXT_ATOMS)
    candidates = tuple(atom for view in pack.layers for atom in view.atoms if _eligible(atom))
    ranked = sorted(candidates, key=lambda atom: _rank_key(atom, tokens))
    lexical = [atom for atom in ranked if tokens & _tokens(atom.claim)]
    if not tokens or not lexical:
        return ()
    selected = _unique(lexical[:limit])
    return _bounded_entries(selected, limit)


def select_style_signals(pack: PersonaPack) -> tuple[PersonaStyleSignal, ...]:
    atoms = tuple(atom for view in pack.layers for atom in view.atoms if _eligible(atom))
    signals: list[PersonaStyleSignal] = []
    for name, pattern, guidance in _STYLE_RULES:
        matches = sorted(
            (atom for atom in atoms if pattern.search(atom.claim)),
            key=lambda atom: (-_timestamp(atom.last_observed_at), atom.atom_id),
        )
        if len(matches) >= 2:
            signals.append(
                PersonaStyleSignal(
                    name=name,
                    guidance=guidance,
                    supports=tuple(_style_support(atom) for atom in matches[:2]),
                )
            )
    return tuple(signals)


def _eligible(atom: PersonaAtom) -> bool:
    return bool(
        atom.source_role == EvidenceRole.DIRECT
        and atom.status
        in {PersonaAtomStatus.OBSERVED, PersonaAtomStatus.PENDING, PersonaAtomStatus.CONFLICTED}
        and atom.evidence_receipts
        and not atom.adopted
        and atom.layer != PersonaLayer.TIMELINE
    )


def _rank_key(atom: PersonaAtom, query_tokens: set[str]) -> tuple[int, int, float, str]:
    overlap = len(query_tokens & _tokens(atom.claim))
    weight = _LAYER_WEIGHT.get(atom.layer, 0)
    recency = _timestamp(atom.last_observed_at)
    return (-overlap, -weight, -recency, atom.atom_id)


def _timestamp(value: datetime | None) -> float:
    return value.timestamp() if value is not None else 0.0


def _tokens(value: str) -> set[str]:
    return {
        normalized
        for item in _TOKEN.findall(value)
        if len(normalized := item.casefold()) > 1 and normalized not in _QUERY_STOPWORDS
    }


def _unique(atoms: list[PersonaAtom]) -> list[PersonaAtom]:
    seen: set[str] = set()
    result: list[PersonaAtom] = []
    for atom in atoms:
        if atom.atom_id not in seen:
            result.append(atom)
            seen.add(atom.atom_id)
    return result


def _bounded_entries(atoms: list[PersonaAtom], limit: int) -> tuple[PersonaContextEntry, ...]:
    result: list[PersonaContextEntry] = []
    remaining = _MAX_CONTEXT_CHARS
    for atom in atoms[:limit]:
        claim = atom.claim[: min(_MAX_CLAIM_CHARS, remaining)].strip()
        if not claim:
            continue
        receipts = tuple(sorted(set(atom.evidence_receipts)))[:_MAX_RECEIPTS_PER_ATOM]
        result.append(
            PersonaContextEntry(
                atom_id=atom.atom_id,
                layer=atom.layer,
                claim=claim,
                truth_status=_truth_status(atom.status),
                evidence_receipts=receipts,
                evidence_receipt_count=len(atom.evidence_receipts),
            )
        )
        remaining -= len(claim)
        if remaining <= 0:
            break
    return tuple(result)


def _truth_status(
    status: PersonaAtomStatus,
) -> Literal["observed", "observed_unadopted", "conflicted_observation"]:
    if status == PersonaAtomStatus.PENDING:
        return "observed_unadopted"
    if status == PersonaAtomStatus.CONFLICTED:
        return "conflicted_observation"
    return "observed"


def _style_support(atom: PersonaAtom) -> PersonaStyleSupport:
    return PersonaStyleSupport(
        atom_id=atom.atom_id,
        evidence_receipts=tuple(sorted(set(atom.evidence_receipts)))[:1],
    )
