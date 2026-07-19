# ruff: noqa: B009, RUF001

from __future__ import annotations

from pathlib import Path

import pytest
from support.full_persona import prepared_full_persona_source
from support.persona_pack import atom_evidence_ids, atom_text, built_pack, pack_atoms

from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona_pack import PersonaLayer

EXPECTED_LAYERS = (
    PersonaLayer.TIMELINE,
    PersonaLayer.AUTOBIOGRAPHY,
    PersonaLayer.VALUES,
    PersonaLayer.GOALS,
    PersonaLayer.DECISIONS,
    PersonaLayer.EVIDENCE,
    PersonaLayer.RISK,
    PersonaLayer.KNOWLEDGE,
    PersonaLayer.SKILLS,
    PersonaLayer.RELATIONSHIPS,
    PersonaLayer.CONTRADICTIONS,
    PersonaLayer.RESPONSE_POLICY,
)


def _layer_name(value):
    return getattr(value, "name", value)


def _section(pack, layer):
    for section in pack.layers:
        if getattr(section, "layer", section) == layer:
            return section
        if getattr(getattr(section, "layer", None), "value", None) == layer.value:
            return section
    raise AssertionError(f"missing persona layer: {layer}")


def test_pack_has_all_layers_in_canonical_order_and_unknown_sections(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)

    actual = tuple(getattr(section, "layer") for section in pack.layers)
    assert actual == EXPECTED_LAYERS
    for layer in EXPECTED_LAYERS:
        section = _section(pack, layer)
        assert getattr(section, "atoms", ()) or getattr(section, "unknowns", ())


def test_assistant_context_is_never_persona_support(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    texts = tuple(atom_text(atom) for atom in pack_atoms(pack))

    assert all("PRIVATE_CONTEXT_" not in text for text in texts)
    for atom in pack_atoms(pack):
        assert atom_evidence_ids(atom)


def test_earliest_observation_is_not_invented_as_birth(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)
    scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    pack = build_deterministic_pack(private_root, manifest.run_id, synthetic=True)

    biography = _section(pack, PersonaLayer.AUTOBIOGRAPHY)
    for atom in getattr(biography, "atoms", ()):
        assert "birth" not in str(getattr(atom, "kind", "")).casefold()
        assert "doğum" not in atom_text(atom).casefold()


def test_mixed_evidence_cannot_populate_identity_layers(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    forbidden = {
        PersonaLayer.AUTOBIOGRAPHY,
        PersonaLayer.VALUES,
        PersonaLayer.RELATIONSHIPS,
        PersonaLayer.SKILLS,
    }
    mixed_atoms = [atom for atom in pack_atoms(pack) if "karma" in atom_text(atom).casefold()]
    assert mixed_atoms
    assert all(getattr(atom, "layer") not in forbidden for atom in mixed_atoms)


@pytest.mark.parametrize(
    "needle,layer",
    (
        ("Doğum günüm", PersonaLayer.AUTOBIOGRAPHY),
        ("Annemle", PersonaLayer.RELATIONSHIPS),
        ("Python biliyorum", PersonaLayer.SKILLS),
    ),
)
def test_explicit_facts_remain_observed_or_pending_without_adoption(
    tmp_path: Path, needle: str, layer: PersonaLayer
) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    matches = [atom for atom in pack_atoms(pack) if needle in atom_text(atom)]

    assert matches
    assert all(getattr(atom, "layer") == layer for atom in matches)
    assert all(getattr(atom, "status") in {"observed", "pending", "candidate"} for atom in matches)
    assert all(hasattr(atom, "adopted") and atom.adopted is False for atom in matches)
    assert all(hasattr(atom, "core_eligible") and atom.core_eligible is False for atom in matches)


def test_knowledge_exposure_does_not_become_skill(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    matches = [atom for atom in pack_atoms(pack) if "Rust hakkında" in atom_text(atom)]

    assert matches
    assert all(getattr(atom, "layer") == PersonaLayer.KNOWLEDGE for atom in matches)
    assert all(getattr(atom, "layer") != PersonaLayer.SKILLS for atom in matches)


def test_project_rule_does_not_become_persona_value(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    matches = [atom for atom in pack_atoms(pack) if "proje kuralı" in atom_text(atom)]

    assert matches
    assert all(getattr(atom, "layer") != PersonaLayer.VALUES for atom in matches)
    assert all(
        getattr(getattr(atom, "target_layer", "project_rule"), "value", "project_rule")
        == "project_rule"
        for atom in matches
    )


def test_conflicting_claims_are_retained_without_last_write_wins(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    matches = [
        atom
        for atom in pack_atoms(pack)
        if "plan yaparım" in atom_text(atom) or "plansız ilerlemeyi" in atom_text(atom)
    ]

    assert len(matches) == 2
    assert all(getattr(atom, "layer") == PersonaLayer.CONTRADICTIONS for atom in matches)
    assert {atom_text(atom) for atom in matches} == {
        "Her zaman önce plan yaparım.",
        "Bazen plansız ilerlemeyi seçerim.",
    }


def test_each_layer_has_a_bounded_atom_count(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    limit = getattr(pack, "max_atoms_per_layer", None)
    if limit is None:
        limit = getattr(getattr(pack, "config", None), "max_atoms_per_layer", 64)

    for section in pack.layers:
        assert len(getattr(section, "atoms", ())) <= limit


def test_response_policy_has_no_execution_authority(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    section = _section(pack, PersonaLayer.RESPONSE_POLICY)

    for atom in getattr(section, "atoms", ()):
        assert getattr(atom, "authority", "none") == "none"
        assert getattr(atom, "action_status", "not_performed") == "not_performed"
