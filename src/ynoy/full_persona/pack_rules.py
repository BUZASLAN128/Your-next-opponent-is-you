# ruff: noqa: RUF001 -- Turkish classification vocabulary is intentional.

from __future__ import annotations

import re

from ynoy.full_persona.identity_rules import (
    has_biography_claim,
    has_relationship_claim,
    has_skill_claim,
    has_value_claim,
    is_imported_identity_text,
    life_facts,
)
from ynoy.models.full_persona import EvidenceRole, FullCorpusEvidence
from ynoy.models.full_persona_pack import PersonaAtomStatus, PersonaLayer
from ynoy.util import sha256_text

_KNOWLEDGE = re.compile(
    r"\b(hakkında okudum|öğrendim|araştırdım|inceledim|biliyorum|bilgim var)\b", re.I
)
_GOAL = re.compile(r"\b(hedefim|istiyorum|planlıyorum|olmak istiyorum|başarmak)\b", re.I)
_RISK = re.compile(
    r"\b(gizlilik|kişisel veri|güvenlik|sızma|hayal gör|halüsin|ram|çök|risk|private)\b",
    re.I,
)
_RESPONSE_POLICY = re.compile(
    r"\b(kanıt|test|doğrula|incele|araştır|push|commit|ram|sınır|dosya|kod kuralı|"
    r"proje kuralı|devam et|sana bırakıyorum)\b",
    re.I,
)
_CONTRADICTION_CANDIDATE = re.compile(
    r"\b(her zaman|bazen|asla|plansız|tercih ederim|seçerim|vazgeçerim)\b", re.I
)
_NEGATION = re.compile(r"\b(değil|istemiyorum|olmasın|asla|plansız|never|not|don't)\b", re.I)
_TOKEN = re.compile(r"[\wçğıöşü]+", re.I)
_SEMANTIC_STOP = {
    "ben",
    "bazen",
    "bir",
    "bu",
    "da",
    "de",
    "ederim",
    "her",
    "için",
    "ilerlemeyi",
    "önce",
    "seçerim",
    "zaman",
}


def primary_layer(evidence: FullCorpusEvidence) -> tuple[PersonaLayer, PersonaAtomStatus]:
    text = evidence.content
    if evidence.role == EvidenceRole.MIXED:
        return PersonaLayer.EVIDENCE, PersonaAtomStatus.OBSERVED
    if evidence.role == EvidenceRole.PROJECT:
        return _project_layer(evidence)
    if is_imported_identity_text(text):
        return PersonaLayer.EVIDENCE, PersonaAtomStatus.OBSERVED
    if _CONTRADICTION_CANDIDATE.search(text):
        return PersonaLayer.CONTRADICTIONS, PersonaAtomStatus.CONFLICTED
    if has_biography_claim(text):
        return PersonaLayer.AUTOBIOGRAPHY, PersonaAtomStatus.PENDING
    if has_relationship_claim(text):
        return PersonaLayer.RELATIONSHIPS, PersonaAtomStatus.PENDING
    if has_skill_claim(text):
        return PersonaLayer.SKILLS, PersonaAtomStatus.PENDING
    if _KNOWLEDGE.search(text):
        return PersonaLayer.KNOWLEDGE, PersonaAtomStatus.OBSERVED
    if has_value_claim(text):
        return PersonaLayer.VALUES, PersonaAtomStatus.PENDING
    if _GOAL.search(text):
        return PersonaLayer.GOALS, PersonaAtomStatus.PENDING
    if _RISK.search(text):
        return PersonaLayer.RISK, PersonaAtomStatus.OBSERVED
    if "decision" in evidence.signal_tags or "correction" in evidence.signal_tags:
        return PersonaLayer.DECISIONS, PersonaAtomStatus.OBSERVED
    return PersonaLayer.EVIDENCE, PersonaAtomStatus.OBSERVED


def claim_for(evidence: FullCorpusEvidence, layer: PersonaLayer, excerpt: str) -> str:
    if layer == PersonaLayer.TIMELINE:
        return f"Observed user conversation evidence at {evidence.event_time.isoformat()}."
    if layer == PersonaLayer.AUTOBIOGRAPHY:
        facts = tuple(fact for _topic, fact in life_facts(excerpt))
        if facts:
            return "; ".join(facts)
    return excerpt


def semantic_key(layer: PersonaLayer, claim: str) -> str:
    if layer != PersonaLayer.CONTRADICTIONS:
        return sha256_text(f"{layer.value}:{claim.casefold()}")
    values = [
        token
        for token in _TOKEN.findall(claim.casefold())
        if token not in _SEMANTIC_STOP and not _NEGATION.fullmatch(token)
    ]
    return sha256_text(f"contradiction:{' '.join(values)}")


def ranking_score(evidence: FullCorpusEvidence, layer: PersonaLayer) -> int:
    score = 10 + 3 * len(evidence.signal_tags)
    if evidence.role == EvidenceRole.DIRECT:
        score += 4
    if layer in {PersonaLayer.AUTOBIOGRAPHY, PersonaLayer.RELATIONSHIPS, PersonaLayer.SKILLS}:
        score += 8
    return score


def _project_layer(evidence: FullCorpusEvidence) -> tuple[PersonaLayer, PersonaAtomStatus]:
    text = evidence.content
    if _RISK.search(text):
        return PersonaLayer.RISK, PersonaAtomStatus.OBSERVED
    if _RESPONSE_POLICY.search(text) or "evidence_demand" in evidence.signal_tags:
        return PersonaLayer.RESPONSE_POLICY, PersonaAtomStatus.OBSERVED
    if "decision" in evidence.signal_tags or "correction" in evidence.signal_tags:
        return PersonaLayer.DECISIONS, PersonaAtomStatus.OBSERVED
    if _GOAL.search(text):
        return PersonaLayer.GOALS, PersonaAtomStatus.OBSERVED
    if _KNOWLEDGE.search(text):
        return PersonaLayer.KNOWLEDGE, PersonaAtomStatus.OBSERVED
    return PersonaLayer.EVIDENCE, PersonaAtomStatus.OBSERVED
