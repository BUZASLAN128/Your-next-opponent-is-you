# ruff: noqa: RUF001 -- Turkish relevance fixtures are intentional.

from __future__ import annotations

from datetime import UTC, datetime

from ynoy.full_persona.response_relevance import diversify_layers, rank_relevant_atoms
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaAtomStatus,
    PersonaEvidenceBasis,
    PersonaLayer,
    PersonaSupportRef,
)
from ynoy.util import canonical_sha256, sha256_text

_OBSERVED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _atom(claim: str, layer: PersonaLayer, seed: str) -> PersonaAtom:
    support_payload = {
        "evidence_id": sha256_text(f"response-relevance-evidence-{seed}"),
        "evidence_sha256": sha256_text(f"response-relevance-payload-{seed}"),
        "source_key": sha256_text(f"response-relevance-source-{seed}"),
        "content_sha256": sha256_text(claim),
        "byte_start": 0,
        "byte_length": len(claim.encode("utf-8")),
        "line_number": 1,
        "event_time": "2026-01-01T00:00:00Z",
        "time_basis": "event",
        "evidence_role": EvidenceRole.DIRECT,
        "char_start": 0,
        "char_end": len(claim),
        "excerpt": claim,
        "excerpt_sha256": sha256_text(claim),
    }
    support = PersonaSupportRef.model_validate(
        {**support_payload, "support_sha256": canonical_sha256(support_payload)}
    )
    atom_payload = {
        "layer": layer,
        "semantic_key": sha256_text(f"response-relevance-semantic-{seed}"),
        "claim": claim,
        "basis": PersonaEvidenceBasis.LITERAL,
        "status": PersonaAtomStatus.OBSERVED,
        "source_role": EvidenceRole.DIRECT,
        "support": (support,),
        "evidence_ids": (support.evidence_id,),
        "evidence_receipts": (support.support_sha256,),
        "observation_count": 1,
        "first_observed_at": _OBSERVED_AT,
        "last_observed_at": _OBSERVED_AT,
    }
    draft = PersonaAtom.model_construct(**atom_payload, atom_id="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"atom_id"})
    return PersonaAtom.model_validate({**normalized, "atom_id": canonical_sha256(normalized)})


def test_sanal_does_not_match_unrelated_sana_claim() -> None:
    atom = _atom("sana", PersonaLayer.VALUES, "sana")

    assert rank_relevant_atoms((atom,), "sanal") == ()


def test_konusma_matches_allowed_plural_inflection() -> None:
    atom = _atom("konuşmalar", PersonaLayer.KNOWLEDGE, "konusmalar")

    assert rank_relevant_atoms((atom,), "konuşma") == (atom,)


def test_multi_concept_query_keeps_coherent_atom_over_one_token_distractors() -> None:
    coherent = _atom(
        "Sanal persona konuşmalar ve geçmiş veriler üzerinden kişiliği taklit eder.",
        PersonaLayer.RESPONSE_POLICY,
        "coherent",
    )
    sanal_distractor = _atom("sanal", PersonaLayer.VALUES, "sanal-distractor")
    gecmis_distractor = _atom("geçmiş", PersonaLayer.GOALS, "gecmis-distractor")

    ranked = rank_relevant_atoms(
        (sanal_distractor, gecmis_distractor, coherent), "sanal konuşma geçmiş"
    )

    assert ranked == (coherent,)


def test_diversification_never_emits_duplicate_atom_ids() -> None:
    values = _atom("value policy", PersonaLayer.VALUES, "values")
    goals = _atom("goal policy", PersonaLayer.GOALS, "goals")
    evidence = _atom("evidence policy", PersonaLayer.EVIDENCE, "evidence")

    selected = diversify_layers((values, values, goals, evidence), limit=3)

    assert tuple(item.atom_id for item in selected) == (
        values.atom_id,
        goals.atom_id,
        evidence.atom_id,
    )
    assert len({item.atom_id for item in selected}) == len(selected)


def test_biography_query_prefers_life_evidence_over_operational_distractors() -> None:
    life = _atom(
        "25 yaşındayım, kendi şirketim var ve gezerek çalışıyorum.",
        PersonaLayer.AUTOBIOGRAPHY,
        "life",
    )
    project = _atom(
        "Sistem hakkında hiçbir şeyi kanıtsız uydurma.",
        PersonaLayer.GOALS,
        "project",
    )

    ranked = rank_relevant_atoms(
        (project, life),
        "Doğumumdan bugüne hayatım hakkında ne biliyorsun? Uydurma.",
    )

    assert ranked == (life,)
