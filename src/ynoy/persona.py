from __future__ import annotations

from collections.abc import Sequence

from ynoy.errors import DataValidationError
from ynoy.manager import build_operating_memory_seed
from ynoy.models import CandidateStatus, CanonicalClaim, PersonaStratum
from ynoy.models.persona import PersonaFacet, PersonaPreview, PersonaView, PersonaViewName
from ynoy.models.review_vocab import TargetLayer

_VIEW_BY_STRATUM = {
    PersonaStratum.DECISIONS_AND_POLICY: PersonaViewName.DECISIONS_AND_POLICY,
    PersonaStratum.VALUES_AND_BELIEFS: PersonaViewName.VALUES_AND_BELIEFS,
    PersonaStratum.GOALS_AND_CONTINUITY: PersonaViewName.GOALS_AND_CONTINUITY,
    PersonaStratum.COMMUNICATION_AND_METACOGNITION: (
        PersonaViewName.COMMUNICATION_AND_METACOGNITION
    ),
    PersonaStratum.SKILLS_NARRATIVE_AND_RELATIONSHIPS: (
        PersonaViewName.SKILLS_NARRATIVE_AND_RELATIONSHIPS
    ),
}

_UNKNOWNS = (
    "behavioral_validation_not_run",
    "temporal_stability_unknown",
    "cross_scope_generalization_not_allowed",
    "protected_control_semantic_screening_not_run",
    "persona_fidelity_unproven",
)


def build_persona_preview(claims: Sequence[CanonicalClaim]) -> PersonaPreview:
    """Project only active canonical persona claims without adding authority."""
    items = tuple(claims)
    _validate_claims(items)
    ordered = tuple(sorted(items, key=_claim_key))
    buckets: dict[PersonaViewName, list[PersonaFacet]] = {name: [] for name in PersonaViewName}
    for claim in ordered:
        facet = _to_facet(claim)
        buckets[_VIEW_BY_STRATUM[facet.stratum]].append(facet)
    views = tuple(PersonaView(name=name, facets=tuple(buckets[name])) for name in PersonaViewName)
    return PersonaPreview(
        subject_id=ordered[0].subject_id,
        data_class=ordered[0].data_class,
        admission_receipts=tuple(sorted({item.admission_receipt_id for item in ordered}, key=str)),
        source_link_ids=tuple(
            sorted({link_id for item in ordered for link_id in item.source_link_ids}, key=str)
        ),
        claim_count=len(ordered),
        views=views,
        missing_views=tuple(view.name for view in views if not view.facets),
        operating_memory=build_operating_memory_seed(),
        unknowns=_UNKNOWNS,
    )


def _validate_claims(claims: tuple[CanonicalClaim, ...]) -> None:
    if not claims:
        raise DataValidationError(
            "canonical_persona_claims_required",
            "Persona preview requires at least one active canonical persona claim.",
        )
    if any(not isinstance(item, CanonicalClaim) for item in claims):
        raise DataValidationError(
            "canonical_persona_claim_required",
            "Persona preview accepts canonical claims only.",
        )
    if any(
        item.status != CandidateStatus.CONFIRMED
        or item.target_layer != TargetLayer.PERSONA_CANDIDATE
        or item.persona_kind is None
        or item.persona_stratum is None
        for item in claims
    ):
        raise DataValidationError(
            "canonical_persona_claim_inactive",
            "Persona preview accepts active classified persona claims only.",
        )
    if len({item.subject_id for item in claims}) != 1:
        raise DataValidationError(
            "persona_subject_mismatch",
            "Persona preview cannot combine canonical claims for different subjects.",
        )
    if len({item.data_class for item in claims}) != 1:
        raise DataValidationError(
            "persona_data_class_mismatch",
            "Persona preview cannot combine synthetic and private identity planes.",
        )
    if len({item.record_id for item in claims}) != len(claims):
        raise DataValidationError(
            "persona_duplicate_claim",
            "Persona preview requires unique canonical claim records.",
        )


def _claim_key(claim: CanonicalClaim) -> tuple[str, str]:
    return str(claim.admission_receipt_id), str(claim.record_id)


def _to_facet(claim: CanonicalClaim) -> PersonaFacet:
    if claim.persona_kind is None or claim.persona_stratum is None:
        raise AssertionError("validated canonical persona claim lost classification")
    return PersonaFacet(
        record_id=claim.record_id,
        admission_receipt_id=claim.admission_receipt_id,
        source_link_ids=claim.source_link_ids,
        subject_id=claim.subject_id,
        kind=claim.persona_kind,
        stratum=claim.persona_stratum,
        statement=claim.literal_statement,
        scope=claim.scope,
        decision_label=claim.decision_label,
        data_class=claim.data_class,
    )
