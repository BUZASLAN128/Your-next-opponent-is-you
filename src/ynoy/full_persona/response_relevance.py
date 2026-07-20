# ruff: noqa: RUF001 -- Turkish tokenization vocabulary is intentional.

from __future__ import annotations

import re
from collections import Counter

from ynoy.models.full_persona_pack import PersonaAtom, PersonaLayer

_TOKEN = re.compile(r"[\wçğıöşü]+", re.I)
_STOPWORDS = {
    "about",
    "adım",
    "adımlar",
    "adımları",
    "answer",
    "atmalıyız",
    "bana",
    "ben",
    "bir",
    "biz",
    "bizim",
    "bu",
    "bundan",
    "cevap",
    "da",
    "de",
    "doğal",
    "et",
    "göre",
    "hangi",
    "için",
    "ile",
    "ilerle",
    "ilerlemeliyiz",
    "kısa",
    "nasıl",
    "net",
    "olarak",
    "oluşturmak",
    "proje",
    "projede",
    "sonra",
    "şu",
    "should",
    "the",
    "ver",
    "ve",
    "what",
    "yapmak",
}
_LAYER_ORDER = (
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
    PersonaLayer.EVIDENCE,
)
_LAYER_WEIGHT = {layer: len(_LAYER_ORDER) - index for index, layer in enumerate(_LAYER_ORDER)}
_INFLECTION_SUFFIXES = {
    "a",
    "da",
    "dan",
    "de",
    "den",
    "dır",
    "dir",
    "dur",
    "dür",
    "e",
    "ı",
    "ım",
    "ın",
    "i",
    "im",
    "in",
    "lar",
    "ler",
    "lik",
    "lık",
    "luk",
    "lük",
    "m",
    "mız",
    "miz",
    "muz",
    "müz",
    "n",
    "ta",
    "tan",
    "te",
    "ten",
    "tır",
    "tir",
    "tur",
    "tür",
    "u",
    "um",
    "un",
    "ü",
    "üm",
    "ün",
    "ya",
    "ye",
}
_CONCEPT_GROUPS = (
    frozenset({"arşiv", "corpus", "geçmiş", "konuşma", "sohbet", "veri"}),
    frozenset({"beyin", "bilinç", "hafıza", "kişilik", "persona", "sanal", "taklit", "zihin"}),
    frozenset(
        {
            "biyografi",
            "büyüme",
            "çalışıyorum",
            "çocukluk",
            "doğum",
            "eğitim",
            "hakkımda",
            "hayat",
            "okul",
            "sınav",
            "şirketim",
            "yaşam",
            "yaşındayım",
        }
    ),
)
_BIOGRAPHY_QUERY_TERMS = _CONCEPT_GROUPS[-1]
_BIOGRAPHY_LAYERS = frozenset(
    {
        PersonaLayer.AUTOBIOGRAPHY,
        PersonaLayer.RELATIONSHIPS,
        PersonaLayer.KNOWLEDGE,
        PersonaLayer.SKILLS,
    }
)


def tokenize(value: str) -> frozenset[str]:
    return frozenset(
        normalized
        for item in _TOKEN.findall(value)
        if len(normalized := item.casefold()) > 1 and normalized not in _STOPWORDS
    )


def rank_relevant_atoms(atoms: tuple[PersonaAtom, ...], query: str) -> tuple[PersonaAtom, ...]:
    """Rank semantic claims by rare query evidence, not generic token overlap."""
    raw_query_tokens = tokenize(query)
    query_tokens = _expand_query_tokens(raw_query_tokens)
    unique = _semantic_representatives(atoms)
    if _concept_matches(raw_query_tokens, _BIOGRAPHY_QUERY_TERMS):
        unique = tuple(atom for atom in unique if atom.layer in _BIOGRAPHY_LAYERS)
    if not query_tokens or not unique:
        return ()
    claim_tokens = {atom.atom_id: tokenize(atom.claim) for atom in unique}
    matched = {
        atom.atom_id: _matched_query_tokens(query_tokens, claim_tokens[atom.atom_id])
        for atom in unique
    }
    frequency = Counter(token for values in matched.values() for token in values)
    rare_limit = max(8, len(unique) // 100)
    eligible = tuple(
        atom for atom in unique if _relevant(matched[atom.atom_id], frequency, rare_limit)
    )
    if any(len(matched[atom.atom_id]) >= 2 for atom in eligible):
        eligible = tuple(atom for atom in eligible if len(matched[atom.atom_id]) >= 2)
    if eligible:
        peak = max(
            _rarity_score(matched[atom.atom_id], frequency, len(unique)) for atom in eligible
        )
        eligible = tuple(
            atom
            for atom in eligible
            if 6 * _rarity_score(matched[atom.atom_id], frequency, len(unique)) >= peak
        )
    return tuple(
        sorted(
            eligible,
            key=lambda atom: _rank_key(atom, matched[atom.atom_id], frequency, len(unique)),
        )
    )


def diversify_layers(atoms: tuple[PersonaAtom, ...], limit: int) -> tuple[PersonaAtom, ...]:
    selected: list[PersonaAtom] = []
    selected_ids: set[str] = set()
    per_layer: Counter[PersonaLayer] = Counter()
    for atom in atoms:
        if atom.atom_id not in selected_ids and per_layer[atom.layer] < 2:
            selected.append(atom)
            selected_ids.add(atom.atom_id)
            per_layer[atom.layer] += 1
        if len(selected) == limit:
            return tuple(selected)
    for atom in atoms:
        if atom.atom_id not in selected_ids:
            selected.append(atom)
            selected_ids.add(atom.atom_id)
    return tuple(selected[:limit])


def _semantic_representatives(atoms: tuple[PersonaAtom, ...]) -> tuple[PersonaAtom, ...]:
    representatives: dict[str, PersonaAtom] = {}
    for atom in atoms:
        current = representatives.get(atom.semantic_key)
        if current is None or _representative_key(atom) > _representative_key(current):
            representatives[atom.semantic_key] = atom
    return tuple(representatives.values())


def _expand_query_tokens(tokens: frozenset[str]) -> frozenset[str]:
    expanded = set(tokens)
    for group in _CONCEPT_GROUPS:
        if _concept_matches(tokens, group):
            expanded.update(group)
    return frozenset(expanded)


def _concept_matches(tokens: frozenset[str], group: frozenset[str]) -> bool:
    return any(
        query == concept or _token_matches(concept, query) for query in tokens for concept in group
    )


def _representative_key(atom: PersonaAtom) -> tuple[int, float, str]:
    observed = atom.last_observed_at.timestamp() if atom.last_observed_at else 0.0
    return atom.observation_count, observed, atom.atom_id


def _matched_query_tokens(
    query_tokens: frozenset[str], claim_tokens: frozenset[str]
) -> frozenset[str]:
    return frozenset(
        query
        for query in query_tokens
        if any(_token_matches(query, claim) for claim in claim_tokens)
    )


def _token_matches(left: str, right: str) -> bool:
    if left == right:
        return True
    suffix = right[len(left) :] if right.startswith(left) else ""
    return len(left) >= 4 and suffix in _INFLECTION_SUFFIXES


def _relevant(tokens: frozenset[str], frequency: Counter[str], rare_limit: int) -> bool:
    return len(tokens) >= 2 or any(frequency[token] <= rare_limit for token in tokens)


def _rank_key(
    atom: PersonaAtom,
    matched: frozenset[str],
    frequency: Counter[str],
    population: int,
) -> tuple[int, int, int, int, float, str]:
    rarity = _rarity_score(matched, frequency, population)
    observed = atom.last_observed_at.timestamp() if atom.last_observed_at else 0.0
    return (
        -rarity,
        -len(matched),
        -_LAYER_WEIGHT.get(atom.layer, 0),
        -atom.observation_count,
        -observed,
        atom.atom_id,
    )


def _rarity_score(matched: frozenset[str], frequency: Counter[str], population: int) -> int:
    return sum(max(1, population // frequency[token]) for token in matched)
