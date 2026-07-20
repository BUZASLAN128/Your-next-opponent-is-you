# ruff: noqa: RUF001 -- Turkish project evidence is intentional.

from __future__ import annotations

import json
import os
from pathlib import Path

from support.full_persona import canonical_file
from support.persona_pack import atom_text, pack_atoms, prepared_pack_source

from ynoy.full_persona.dossier import build_persona_dossier
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.reaction_evidence import compact_reaction_events
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.response_context import select_response_context
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona_pack import PersonaLayer


def _append_project_instruction(source_root: Path) -> None:
    path = canonical_file(source_root, 0)
    original_mtime = path.stat().st_mtime_ns
    payload = {
        "type": "response_item",
        "timestamp": "2026-01-01T03:30:00+00:00",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Proje kuralı: test ve kod doğrula; devam et.",
                }
            ],
        },
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.utime(path, ns=(original_mtime, original_mtime))


def _built_project_fixture(tmp_path: Path):
    source_root, private_root, prepared = prepared_pack_source(tmp_path)
    _append_project_instruction(source_root)
    manifest = freeze_full_corpus(
        source_root,
        private_root,
        prepared.manifest.study_id,
        synthetic=True,
    )
    corpus = FullPersonaStore(private_root, synthetic=True)
    corpus.write_manifest(manifest)
    head = scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    pack = build_deterministic_pack(private_root, manifest.run_id, synthetic=True)
    return corpus, manifest, head, pack


def _project_atoms(pack):
    return [
        atom
        for atom in pack_atoms(pack)
        if "Proje kuralı" in atom_text(atom) and atom.layer != PersonaLayer.TIMELINE
    ]


def _assert_pack_projection(pack) -> None:
    project_atoms = _project_atoms(pack)
    forbidden = {
        PersonaLayer.AUTOBIOGRAPHY,
        PersonaLayer.VALUES,
        PersonaLayer.SKILLS,
        PersonaLayer.RELATIONSHIPS,
    }

    assert project_atoms
    assert all(atom.source_role == "project_instruction" for atom in project_atoms)
    assert all(
        atom.layer in {PersonaLayer.DECISIONS, PersonaLayer.RESPONSE_POLICY}
        for atom in project_atoms
    )
    assert not any(atom.layer in forbidden for atom in project_atoms)


def _assert_dossier_projection(pack) -> None:
    dossier = build_persona_dossier(pack)
    project_topics = {
        topic.key
        for topic in dossier.topics
        if any("Proje kuralı" in candidate.claim for candidate in topic.candidates)
    }
    project_candidates = [
        candidate
        for topic in dossier.topics
        for candidate in topic.candidates
        if "Proje kuralı" in candidate.claim
    ]
    assert project_candidates
    assert project_topics <= {"work_projects", "decision_behavior", "risk_boundaries"}
    assert all(candidate.source_role == "project_instruction" for candidate in project_candidates)


def _assert_response_projection(pack) -> None:
    context = select_response_context(pack, "proje kuralı test kod doğrula")
    assert any(
        entry.source_role == "project_instruction" and "Proje kuralı" in entry.claim
        for entry in context
    )


def _assert_reaction_projection(corpus, manifest, head) -> None:
    evidence = iter_verified_evidence(corpus, manifest, head)
    sources = {item.source_key: item for item in manifest.files}
    events = compact_reaction_events(evidence, sources, manifest)
    project_events = [item for item in events if "Proje kuralı" in item.content_excerpt]
    assert project_events
    assert all(
        item.signal in {"correction", "decision", "evidence_demand"} for item in project_events
    )


def test_project_instruction_is_operational_not_personal_identity(tmp_path: Path) -> None:
    corpus, manifest, head, pack = _built_project_fixture(tmp_path)
    _assert_pack_projection(pack)
    _assert_dossier_projection(pack)
    _assert_response_projection(pack)
    _assert_reaction_projection(corpus, manifest, head)
