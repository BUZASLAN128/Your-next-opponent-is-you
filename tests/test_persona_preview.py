from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.models import (
    AdoptedPersonaDeclaration,
    BootstrapDeclaration,
    CandidateKind,
    CandidateStatus,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    EvidenceRegime,
    PersonaFacet,
    PersonaViewName,
    ScopeRef,
    SourceAuthority,
    Speaker,
)
from ynoy.persona import build_persona_preview

VIEW_KINDS = (
    (PersonaViewName.BEHAVIORAL_PATTERNS, (CandidateKind.TRAIT,)),
    (PersonaViewName.VALUES, (CandidateKind.VALUE,)),
    (PersonaViewName.AUTOBIOGRAPHICAL, (CandidateKind.NARRATIVE,)),
    (PersonaViewName.PERSONAL_METACOGNITION, (CandidateKind.METACOGNITION,)),
)
SCOPED_KINDS = (
    CandidateKind.BELIEF,
    CandidateKind.PREFERENCE,
    CandidateKind.GOAL,
    CandidateKind.RELATIONSHIP,
    CandidateKind.SKILL,
)


def _declaration(
    index: int,
    kind: CandidateKind = CandidateKind.TRAIT,
    *,
    synthetic: bool = True,
    subject_id: str = "self",
    status: CandidateStatus = CandidateStatus.CONFIRMED,
) -> AdoptedPersonaDeclaration:
    return AdoptedPersonaDeclaration(
        record_id=UUID(int=index),
        source_record_id=UUID(int=10_000 + index),
        subject_id=subject_id,
        kind=kind,
        statement=f"Exact declaration {index}: {kind.value}.",
        scope=ScopeRef(
            person_id=subject_id,
            project=f"project-{index}",
            role="reviewer",
            risk="high",
        ),
        decision_label=DecisionLabel.REJECT,
        source_name=f"source-{index}.json",
        data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY),
        synthetic=synthetic,
        status=status,
    )


def _run_cli(
    arguments: Sequence[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    exit_code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return exit_code, payload


def _remove_optional_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "YNOY_DATABASE_URL",
        "YNOY_PRIVATE_ROOT",
        "YNOY_LOCAL_REASONER_URL",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_preview_has_canonical_views_and_is_independent_of_input_order() -> None:
    kinds = tuple(kind for _, view_kinds in VIEW_KINDS for kind in view_kinds) + SCOPED_KINDS
    declarations = tuple(_declaration(index, kind) for index, kind in enumerate(kinds, start=1))

    forward = build_persona_preview(declarations)
    reverse = build_persona_preview(tuple(reversed(declarations)))

    assert forward == reverse
    assert (
        tuple((view.name, tuple(facet.kind for facet in view.facets)) for view in forward.views)
        == VIEW_KINDS
    )
    assert tuple(facet.kind for facet in forward.scoped_objects) == SCOPED_KINDS
    assert forward.declaration_count == len(kinds)
    assert forward.missing_views == ()


@pytest.mark.parametrize(
    ("synthetic", "expected_class"),
    [
        (True, DataClass.PUBLIC_SYNTHETIC),
        (False, DataClass.DERIVED_IDENTITY),
    ],
)
def test_preview_preserves_declared_source_fields_without_identity_summary(
    synthetic: bool,
    expected_class: DataClass,
) -> None:
    declaration = _declaration(101, synthetic=synthetic)
    preview = build_persona_preview((declaration,))
    facet = preview.views[0].facets[0]

    assert facet.statement == declaration.statement
    assert facet.scope == declaration.scope
    assert facet.decision_label == declaration.decision_label
    assert facet.record_id == declaration.record_id
    assert facet.source_record_id == declaration.source_record_id
    assert facet.source_name == declaration.source_name
    assert facet.data_class == expected_class and preview.data_class == expected_class
    assert facet.speaker == Speaker.USER
    assert facet.claim_holder == ClaimHolder.REPRESENTED_USER
    assert facet.adopted is True
    assert facet.evidence_plane == "identity_interpretation"
    assert facet.source_authority == SourceAuthority.EXPLICIT_USER_STATEMENT
    assert preview.source_receipts == (declaration.source_record_id,)
    assert '"summary"' not in json.dumps(preview.model_dump(mode="json"), ensure_ascii=False)


def test_operating_memory_is_separate_system_control_and_never_a_facet() -> None:
    preview = build_persona_preview((_declaration(201, synthetic=False),))
    facets = tuple(facet for view in preview.views for facet in view.facets)
    facets += preview.scoped_objects
    memory = preview.operating_memory

    assert memory.memory_kind == "system_operating_seed"
    assert memory.source_authority == SourceAuthority.SYSTEM_CONTROL
    assert memory.data_class == DataClass.PUBLIC_SYNTHETIC
    assert memory.evidence_regime == EvidenceRegime.ZERO
    assert memory.persona_memory_state == "empty" and memory.persona_evidence_count == 0
    assert all(not isinstance(rule, PersonaFacet) for rule in memory.rules)
    assert all(rule.source_authority == SourceAuthority.SYSTEM_CONTROL for rule in memory.rules)
    assert all(rule.data_class == DataClass.PUBLIC_SYNTHETIC for rule in memory.rules)
    assert all(
        facet.source_authority == SourceAuthority.EXPLICIT_USER_STATEMENT for facet in facets
    )


def _invalid_declarations(case: str) -> tuple[AdoptedPersonaDeclaration, ...]:
    first = _declaration(301)
    if case == "empty":
        return ()
    if case == "mixed_subject":
        return first, _declaration(302, subject_id="someone-else")
    if case == "mixed_data_class":
        return first, _declaration(302, synthetic=False)
    if case == "duplicate_record":
        duplicate = _declaration(302).model_copy(update={"record_id": first.record_id})
        return first, duplicate
    inactive = first.model_copy(update={"status": CandidateStatus.INVALIDATED})
    return (inactive,)


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("empty", "persona_declarations_required"),
        ("mixed_subject", "persona_subject_mismatch"),
        ("mixed_data_class", "persona_data_class_mismatch"),
        ("duplicate_record", "persona_duplicate_declaration"),
        ("inactive", "persona_inactive_declaration"),
    ],
)
def test_preview_rejects_invalid_declaration_sets(case: str, error_code: str) -> None:
    with pytest.raises(DataValidationError) as blocked:
        build_persona_preview(_invalid_declarations(case))
    assert blocked.value.code == error_code


def test_preview_rejects_legacy_bootstrap_declaration() -> None:
    legacy = BootstrapDeclaration(
        kind=CandidateKind.TRAIT,
        statement="Legacy declaration without explicit adoption.",
        source_name="legacy.json",
    )
    with pytest.raises(DataValidationError) as blocked:
        build_persona_preview((legacy,))  # type: ignore[arg-type]
    assert blocked.value.code == "persona_adopted_declaration_required"


def test_persona_cli_synthetic_preview_needs_no_database_root_or_provider(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "declared-persona.json"
    source.write_text(
        json.dumps(
            [
                {
                    "kind": "trait",
                    "statement": "Prefer evidence.",
                    "speaker": "user",
                    "claim_holder": "represented_user",
                    "source_authority": "explicit_user_statement",
                    "adopted": True,
                    "evidence_plane": "identity_interpretation",
                    "synthetic": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    dependency_calls: list[str] = []

    def forbidden_dependency(*_: object, **__: object) -> None:
        dependency_calls.append("called")
        raise AssertionError("persona preview must not call storage or a provider")

    _remove_optional_dependencies(monkeypatch)
    monkeypatch.setattr("ynoy.storage.database.psycopg.connect", forbidden_dependency)
    monkeypatch.setattr("ynoy.local_http.build_opener", forbidden_dependency)
    monkeypatch.setattr("ynoy.config.Settings.require_private_root", forbidden_dependency)
    exit_code, payload = _run_cli(["persona", "preview", str(source), "--synthetic"], capsys)

    assert exit_code == 0 and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    assert result["persona_state"] == "declared_only"
    assert result["evidence_regime"] == "declared"
    assert result["confidence_status"] == "low_unvalidated"
    assert result["data_class"] == "D0"
    assert result["database_used"] is False and result["provider_used"] is False
    assert result["persistence_status"] == "not_persisted"
    assert result["authority"] == "none" and result["automatic_core_promotion"] is False
    assert dependency_calls == []
