# ruff: noqa: B009, RUF001

from __future__ import annotations

from pathlib import Path

from support.persona_pack import atom_evidence_ids, atom_text, built_pack

from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.retrieval import retrieve_persona_atoms


def test_pack_build_is_deterministic_for_identical_synthetic_content(tmp_path: Path) -> None:
    _source, private_root, manifest, first = built_pack(tmp_path)
    second = build_deterministic_pack(private_root, manifest.run_id, synthetic=True)

    assert first.pack_sha256 == second.pack_sha256
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_retrieval_is_bounded_and_only_returns_evidence_bound_atoms(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    selected = retrieve_persona_atoms(pack, "test Python doğum", top_k=2)

    assert len(selected) <= 2
    assert len({getattr(atom, "atom_id") for atom in selected}) == len(selected)
    assert all(atom_evidence_ids(atom) for atom in selected)
    assert all(atom_text(atom).strip() for atom in selected)


def test_retrieval_does_not_return_unknown_or_unbound_sections(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)
    selected = retrieve_persona_atoms(pack, "not represented in corpus", top_k=5)

    assert len(selected) <= 5
    assert all(atom_evidence_ids(atom) for atom in selected)
    assert all(getattr(atom, "status") != "unknown" for atom in selected)


def test_retrieval_excludes_mixed_pending_and_conflicted_atoms(tmp_path: Path) -> None:
    _source, _private, _manifest, pack = built_pack(tmp_path)

    for query in ("karma içerik", "Python biliyorum", "plansız ilerlemeyi"):
        assert retrieve_persona_atoms(pack, query, top_k=5) == ()
