# ruff: noqa: RUF001 -- Turkish evidence vocabulary is intentional.

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.response_context import select_style_signals
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaAtomStatus,
    PersonaEvidenceBasis,
    PersonaLayer,
    PersonaPack,
)
from ynoy.models.persona_dossier import (
    DOSSIER_TOPIC_ORDER,
    DossierTopicKey,
    PersonaDossier,
    PersonaDossierCandidate,
    PersonaDossierStyleSignal,
    PersonaDossierStyleSupport,
    PersonaDossierTopic,
)
from ynoy.util import canonical_sha256, utc_now

_MAX_CANDIDATES_PER_TOPIC = 8
_MAX_CLAIM_CHARS = 1_200
_JSON_OBJECT_ADAPTER = TypeAdapter(dict[str, Any])


@dataclass(frozen=True, slots=True)
class _TopicRule:
    key: DossierTopicKey
    layers: frozenset[PersonaLayer]
    pattern: re.Pattern[str] | None = None


_BIOGRAPHY_LAYERS = frozenset(
    {PersonaLayer.AUTOBIOGRAPHY, PersonaLayer.KNOWLEDGE, PersonaLayer.EVIDENCE}
)
_TOPIC_RULES = (
    _TopicRule("birth", _BIOGRAPHY_LAYERS, re.compile(r"\b(doğdum|doğum\w*|born)\b", re.I)),
    _TopicRule(
        "childhood",
        _BIOGRAPHY_LAYERS,
        re.compile(r"\b(çocukluğ\w*|küçükken|büyüdüm|büyürken)\b", re.I),
    ),
    _TopicRule(
        "education",
        _BIOGRAPHY_LAYERS,
        re.compile(
            r"\b(mezunum|mezun oldum|öğrenciyim|öğrenciydim|eğitim aldım|"
            r"üniversiteye gittim|(?:okul|lise|üniversite|bölüm)\w*.{0,60}"
            r"(?:okudum|mezun\w*))\b",
            re.I,
        ),
    ),
    _TopicRule(
        "exams",
        _BIOGRAPHY_LAYERS,
        re.compile(r"\b(sınav\w*|yks|öss|kpss|ales|toefl|ielts|gre|sat)\b", re.I),
    ),
    _TopicRule(
        "work_projects",
        frozenset(layer for layer in PersonaLayer if layer != PersonaLayer.TIMELINE),
        re.compile(
            r"\b(iş\w*|çalış\w*|meslek\w*|proje\w*|repo\w*|ürün\w*|müşteri\w*|"
            r"kod\w*|yazılım\w*|uygulama\w*)\b",
            re.I,
        ),
    ),
    _TopicRule("knowledge", frozenset({PersonaLayer.KNOWLEDGE})),
    _TopicRule(
        "skills",
        frozenset({PersonaLayer.SKILLS}),
        re.compile(
            r"\b(uzmanım|yetkinim|hakimim|yıllardır .{0,80} kullanıyorum|"
            r"profesyonel olarak .{0,80} yapıyorum)\b",
            re.I,
        ),
    ),
    _TopicRule(
        "values",
        frozenset({PersonaLayer.VALUES}),
        re.compile(
            r"\b(önemsiyorum|değer veriyorum|inanıyorum|benim için önemli|"
            r"vazgeçilmez|asla kabul etmem)\b",
            re.I,
        ),
    ),
    _TopicRule("goals", frozenset({PersonaLayer.GOALS})),
    _TopicRule("decision_behavior", frozenset({PersonaLayer.DECISIONS})),
    _TopicRule("risk_boundaries", frozenset({PersonaLayer.RISK})),
    _TopicRule(
        "relationships",
        frozenset({PersonaLayer.RELATIONSHIPS}),
        re.compile(
            r"\b(annem|babam|kardeşim|eşim|sevgilim|ailem|benim oğlum|benim kızım|"
            r"oğlum var|kızım var|(?:bir )?arkadaşım(?:la| ile)?.{0,80}"
            r"(?:beraber|birlikte|çalış\w*))\b",
            re.I,
        ),
    ),
    _TopicRule("contradictions", frozenset({PersonaLayer.CONTRADICTIONS})),
)


def build_persona_dossier(pack: PersonaPack) -> PersonaDossier:
    """Project a private pack into a bounded, evidence-first and non-persistent dossier."""
    validated = _validated_pack(pack)
    atoms = tuple(atom for view in validated.layers for atom in view.atoms if _eligible(atom))
    topics = tuple(_literal_topic(rule, atoms) for rule in _TOPIC_RULES)
    topics += (_style_topic(validated),)
    if tuple(topic.key for topic in topics) != DOSSIER_TOPIC_ORDER:
        raise DataValidationError(
            "persona_dossier_topic_order_invalid", "Persona dossier topic order is invalid."
        )
    payload: dict[str, object] = {
        "protocol_version": "persona-dossier/0.1",
        "pack_id": validated.pack_id,
        "pack_sha256": validated.pack_sha256,
        "source_run_id": validated.source_run_id,
        "source_manifest_sha256": validated.source_manifest_sha256,
        "source_head_sha256": validated.source_head_sha256,
        "source_head_revision": validated.source_head_revision,
        "expires_at": validated.expires_at,
        "data_class": validated.data_class,
        "synthetic": validated.synthetic,
        "processed_evidence_count": validated.processed_evidence_count,
        "retained_atom_count": validated.retained_atom_count,
        "topics": topics,
        "model_enrichment": "not_used",
        "calibration_status": "not_calibrated",
        "semantic_adoption": "not_established",
        "persona_quality_claimed": False,
        "automatic_core_promotion": False,
        "authority": "none",
        "persistent": False,
    }
    normalized = _JSON_OBJECT_ADAPTER.dump_python(payload, mode="json")
    return PersonaDossier.model_validate(
        {**normalized, "dossier_sha256": canonical_sha256(normalized)}
    )


def _validated_pack(pack: PersonaPack) -> PersonaPack:
    try:
        validated = PersonaPack.model_validate(pack.model_dump(mode="json"))
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "persona_dossier_pack_invalid",
            "Persona dossier requires a canonical provenance-bound pack.",
        ) from exc
    if validated.expires_at <= utc_now():
        raise DataValidationError(
            "persona_dossier_pack_expired", "An expired pack cannot produce a persona dossier."
        )
    return validated


def _eligible(atom: PersonaAtom) -> bool:
    return bool(
        atom.source_role == EvidenceRole.DIRECT
        and atom.basis == PersonaEvidenceBasis.LITERAL
        and atom.status
        in {PersonaAtomStatus.OBSERVED, PersonaAtomStatus.PENDING, PersonaAtomStatus.CONFLICTED}
        and atom.evidence_receipts
        and atom.first_observed_at is not None
        and atom.last_observed_at is not None
        and not atom.adopted
        and atom.layer != PersonaLayer.TIMELINE
    )


def _literal_topic(rule: _TopicRule, atoms: tuple[PersonaAtom, ...]) -> PersonaDossierTopic:
    matches = tuple(atom for atom in atoms if _matches(rule, atom))
    ranked = tuple(sorted(matches, key=_rank_key))
    candidates = tuple(_candidate(atom) for atom in ranked[:_MAX_CANDIDATES_PER_TOPIC])
    state: Literal[
        "literal_candidates", "conflicted_candidates", "derived_unadopted", "unknown"
    ] = "unknown"
    if candidates:
        state = (
            "conflicted_candidates"
            if any(item.truth_status == "conflicted_observation" for item in candidates)
            else "literal_candidates"
        )
    return PersonaDossierTopic(
        key=rule.key,
        evidence_state=state,
        total_candidate_count=len(matches),
        candidates=candidates,
        style_signals=(),
        unknowns=_topic_unknowns(rule.key, bool(matches)),
    )


def _style_topic(pack: PersonaPack) -> PersonaDossierTopic:
    signals = tuple(
        PersonaDossierStyleSignal(
            name=signal.name,
            guidance=signal.guidance,
            supports=tuple(
                PersonaDossierStyleSupport(
                    atom_id=support.atom_id,
                    evidence_receipts=support.evidence_receipts,
                )
                for support in signal.supports
            ),
        )
        for signal in select_style_signals(pack)
    )
    return PersonaDossierTopic(
        key="response_style",
        evidence_state="derived_unadopted" if signals else "unknown",
        total_candidate_count=0,
        candidates=(),
        style_signals=signals,
        unknowns=(
            "style_not_calibrated_for_generation",
            "style_semantic_adoption_not_established",
        )
        if signals
        else (
            "response_style_not_supported_by_repeated_direct_observations",
            "retained_pack_projection_not_semantically_exhaustive",
        ),
    )


def _matches(rule: _TopicRule, atom: PersonaAtom) -> bool:
    return atom.layer in rule.layers and (
        rule.pattern is None or rule.pattern.search(atom.claim) is not None
    )


def _rank_key(atom: PersonaAtom) -> tuple[float, int, str]:
    observed = atom.last_observed_at.timestamp() if atom.last_observed_at else 0.0
    return (-observed, -atom.observation_count, atom.atom_id)


def _candidate(atom: PersonaAtom) -> PersonaDossierCandidate:
    if atom.first_observed_at is None or atom.last_observed_at is None:
        raise DataValidationError(
            "persona_dossier_atom_invalid", "Persona dossier atom lacks an observation interval."
        )
    receipts = tuple(sorted(set(atom.evidence_receipts)))[:4]
    return PersonaDossierCandidate(
        atom_id=atom.atom_id,
        layer=atom.layer,
        claim=atom.claim[:_MAX_CLAIM_CHARS],
        truth_status=_truth_status(atom.status),
        evidence_receipts=receipts,
        evidence_receipt_count=len(atom.evidence_receipts),
        first_observed_at=atom.first_observed_at,
        last_observed_at=atom.last_observed_at,
    )


def _truth_status(
    status: PersonaAtomStatus,
) -> Literal["observed", "observed_unadopted", "conflicted_observation"]:
    if status == PersonaAtomStatus.PENDING:
        return "observed_unadopted"
    if status == PersonaAtomStatus.CONFLICTED:
        return "conflicted_observation"
    return "observed"


def _topic_unknowns(key: DossierTopicKey, has_candidates: bool) -> tuple[str, ...]:
    if has_candidates:
        specific = {
            "skills": "skill_performance_not_demonstrated",
            "values": "stable_value_not_adopted",
            "goals": "current_goal_status_unknown",
            "relationships": "relationship_truth_not_established",
            "contradictions": "contradiction_relation_not_established",
        }.get(key)
        return tuple(
            item
            for item in ("current_meaning_and_adoption_unreviewed", specific)
            if item is not None
        )
    return (
        f"{key}_not_established_by_literal_direct_evidence",
        "retained_pack_projection_not_semantically_exhaustive",
    )
