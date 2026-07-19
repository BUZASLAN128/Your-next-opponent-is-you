# ruff: noqa: RUF001 -- Turkish tokenization vocabulary is intentional.

from __future__ import annotations

import re

from ynoy.errors import DataValidationError
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaAtomStatus,
    PersonaLayer,
    PersonaPack,
)

_TOKEN = re.compile(r"[\wçğıöşü]+", re.I)
_UNADOPTED_IDENTITY_LAYERS = {
    PersonaLayer.AUTOBIOGRAPHY,
    PersonaLayer.VALUES,
    PersonaLayer.SKILLS,
    PersonaLayer.RELATIONSHIPS,
    PersonaLayer.CONTRADICTIONS,
}


def retrieve_persona_atoms(
    pack: PersonaPack,
    query: str,
    *,
    top_k: int | None = None,
) -> tuple[PersonaAtom, ...]:
    """Return bounded lexical evidence without inventing a public judgment basis."""
    if not query.strip():
        raise DataValidationError(
            "persona_retrieval_query_empty", "Persona retrieval requires a non-empty query."
        )
    limit = pack.config.max_retrieval_hits if top_k is None else top_k
    if limit < 1 or limit > pack.config.max_retrieval_hits:
        raise DataValidationError(
            "persona_retrieval_limit_invalid", "Persona retrieval exceeded its frozen limit."
        )
    query_tokens = _tokens(query)
    ranked: list[tuple[int, int, str, PersonaAtom]] = []
    for layer_index, section in enumerate(pack.layers):
        for atom in section.atoms:
            if not _safe_for_retrieval(atom):
                continue
            score = len(query_tokens & _tokens(atom.claim))
            if score:
                ranked.append((score, -layer_index, atom.atom_id, atom))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return tuple(item[3] for item in ranked[:limit])


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN.findall(value) if len(token) > 1}


def _safe_for_retrieval(atom: PersonaAtom) -> bool:
    return bool(
        atom.status == PersonaAtomStatus.OBSERVED
        and atom.source_role != EvidenceRole.MIXED
        and atom.layer not in _UNADOPTED_IDENTITY_LAYERS
        and atom.evidence_receipts
        and not atom.adopted
    )
