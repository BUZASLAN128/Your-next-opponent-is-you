from __future__ import annotations

from collections.abc import Sequence

from ynoy.errors import DataValidationError
from ynoy.manager import build_operating_memory_seed
from ynoy.models import AdoptedPersonaDeclaration, CandidateKind, CandidateStatus
from ynoy.models.persona import PersonaFacet, PersonaPreview, PersonaView, PersonaViewName

_VIEW_BY_KIND = {
    CandidateKind.TRAIT: PersonaViewName.BEHAVIORAL_PATTERNS,
    CandidateKind.VALUE: PersonaViewName.VALUES,
    CandidateKind.NARRATIVE: PersonaViewName.AUTOBIOGRAPHICAL,
    CandidateKind.METACOGNITION: PersonaViewName.PERSONAL_METACOGNITION,
}

_UNKNOWNS = (
    "behavioral_validation_not_run",
    "temporal_stability_unknown",
    "cross_scope_generalization_not_allowed",
    "protected_control_semantic_screening_not_run",
    "persona_fidelity_unproven",
)


def build_persona_preview(declarations: Sequence[AdoptedPersonaDeclaration]) -> PersonaPreview:
    """Project explicit declarations without inferring or persisting a persona."""
    items = tuple(declarations)
    _validate_declarations(items)
    ordered = tuple(sorted(items, key=_declaration_key))
    buckets: dict[PersonaViewName, list[PersonaFacet]] = {name: [] for name in PersonaViewName}
    scoped_objects: list[PersonaFacet] = []
    for declaration in ordered:
        facet = _to_facet(declaration)
        view_name = _VIEW_BY_KIND.get(declaration.kind)
        if view_name is None:
            scoped_objects.append(facet)
        else:
            buckets[view_name].append(facet)
    views = tuple(PersonaView(name=name, facets=tuple(buckets[name])) for name in PersonaViewName)
    missing_views = tuple(view.name for view in views if not view.facets)
    source_receipts = tuple(sorted({item.source_record_id for item in ordered}, key=str))
    return PersonaPreview(
        subject_id=ordered[0].subject_id,
        data_class=ordered[0].data_class,
        source_receipts=source_receipts,
        declaration_count=len(ordered),
        views=views,
        scoped_objects=tuple(scoped_objects),
        missing_views=missing_views,
        operating_memory=build_operating_memory_seed(),
        unknowns=_UNKNOWNS,
    )


def _validate_declarations(declarations: tuple[AdoptedPersonaDeclaration, ...]) -> None:
    if not declarations:
        raise DataValidationError(
            "persona_declarations_required",
            "Persona preview requires at least one explicit declaration.",
        )
    if any(not isinstance(item, AdoptedPersonaDeclaration) for item in declarations):
        raise DataValidationError(
            "persona_adopted_declaration_required",
            "Persona preview accepts explicitly adopted persona declarations only.",
        )
    _validate_declaration_content(declarations)
    _validate_declaration_set(declarations)


def _validate_declaration_content(
    declarations: tuple[AdoptedPersonaDeclaration, ...],
) -> None:
    if any(not item.subject_id.strip() for item in declarations):
        raise DataValidationError(
            "persona_subject_required",
            "Persona preview declarations require a non-empty subject.",
        )
    if any(not item.source_name.strip() for item in declarations):
        raise DataValidationError(
            "persona_source_required",
            "Persona preview declarations require a named source.",
        )
    if any(not item.statement.strip() for item in declarations):
        raise DataValidationError(
            "persona_statement_required",
            "Persona preview declarations require a non-empty statement.",
        )


def _validate_declaration_set(declarations: tuple[AdoptedPersonaDeclaration, ...]) -> None:
    if any(item.status != CandidateStatus.CONFIRMED for item in declarations):
        raise DataValidationError(
            "persona_inactive_declaration",
            "Persona preview accepts confirmed declarations only.",
        )
    if len({item.subject_id for item in declarations}) != 1:
        raise DataValidationError(
            "persona_subject_mismatch",
            "Persona preview cannot combine declarations for different subjects.",
        )
    if len({item.data_class for item in declarations}) != 1:
        raise DataValidationError(
            "persona_data_class_mismatch",
            "Persona preview cannot combine public synthetic and private identity data.",
        )
    record_ids = {item.record_id for item in declarations}
    if len(record_ids) != len(declarations):
        raise DataValidationError(
            "persona_duplicate_declaration",
            "Persona preview requires unique declaration records.",
        )


def _declaration_key(declaration: AdoptedPersonaDeclaration) -> tuple[str, str]:
    return str(declaration.source_record_id), str(declaration.record_id)


def _to_facet(declaration: AdoptedPersonaDeclaration) -> PersonaFacet:
    return PersonaFacet(
        record_id=declaration.record_id,
        source_record_id=declaration.source_record_id,
        source_name=declaration.source_name,
        subject_id=declaration.subject_id,
        speaker=declaration.speaker,
        claim_holder=declaration.claim_holder,
        adopted=declaration.adopted,
        evidence_plane=declaration.evidence_plane,
        kind=declaration.kind,
        statement=declaration.statement,
        scope=declaration.scope,
        decision_label=declaration.decision_label,
        status=CandidateStatus.CONFIRMED,
        data_class=declaration.data_class,
    )
