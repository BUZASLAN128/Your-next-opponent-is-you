# ruff: noqa: RUF001

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from support.full_persona import canonical_file
from support.persona_study import synthetic_codex_study_root
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.persona_study.prepare import PreparedPersonaStudy, prepare_persona_study
from ynoy.util import utc_now


def prepared_pack_source(tmp_path: Path) -> tuple[Path, Path, PreparedPersonaStudy]:
    source_root, _ = synthetic_codex_study_root(tmp_path)
    path = canonical_file(source_root, 0)
    with path.open("a", encoding="utf-8") as stream:
        for minute, text in enumerate(
            (
                "Doğum günüm 1990-01-02.",
                "Annemle ilişkim yakın; bunu kendi sözüm olarak belirtiyorum.",
                "Python biliyorum ve bunu yıllardır kullanıyorum.",
                "Rust hakkında okudum, ama hiç uygulamadım.",
                "Her zaman önce plan yaparım.",
                "Bazen plansız ilerlemeyi seçerim.",
                "PLEASE IMPLEMENT THIS PLAN: proje kuralı olarak test zorunlu.",
                "# Files mentioned by the user:\n# My request: karma içerik.",
            ),
            start=10,
        ):
            payload = {
                "type": "response_item",
                "timestamp": f"2026-01-01T03:{minute:02d}:00+00:00",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
            stream.write(json.dumps(payload, separators=(",", ":")) + "\n")
    stable_ns = int(datetime(2026, 1, 1, 3, 4, 5, tzinfo=UTC).timestamp() * 1_000_000_000)
    os.utime(path, ns=(stable_ns, stable_ns))
    private_root = tmp_path / "private"
    prepared = prepare_persona_study(
        source_root,
        private_root,
        synthetic=True,
        evaluation_time=utc_now(),
    )
    return source_root, private_root, prepared


def built_pack(tmp_path: Path):
    source_root, private_root, prepared = prepared_pack_source(tmp_path)
    manifest = freeze_full_corpus(
        source_root, private_root, prepared.manifest.study_id, synthetic=True
    )
    corpus_store = FullPersonaStore(private_root, synthetic=True)
    corpus_store.write_manifest(manifest)
    scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    pack = build_deterministic_pack(private_root, manifest.run_id, synthetic=True)
    return source_root, private_root, manifest, pack


def pack_atoms(pack):
    atoms = getattr(pack, "atoms", None)
    if atoms is not None:
        return tuple(atoms)
    return tuple(atom for section in pack.layers for atom in section.atoms)


def atom_text(atom) -> str:
    for name in ("claim", "statement", "text", "content"):
        value = getattr(atom, name, None)
        if isinstance(value, str):
            return value
    raise AssertionError("persona atom has no text field")


def atom_evidence_ids(atom) -> tuple[str, ...]:
    for name in ("evidence_ids", "evidence_receipts", "source_receipts"):
        value = getattr(atom, name, None)
        if value is not None:
            return tuple(str(item) for item in value)
    raise AssertionError("persona atom is not provenance-bound")
