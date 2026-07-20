from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.persona_pack import built_pack
from support.persona_study import synthetic_codex_study_root

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.study_full_persona_package import (
    build_full_persona_package_handler,
)
from ynoy.cli.parser import parse_args
from ynoy.config import Settings
from ynoy.errors import DataValidationError
from ynoy.full_persona.deletion import delete_full_persona_run
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.persona_package import (
    build_full_persona_package,
    render_persona_brain_atlas,
)
from ynoy.full_persona.persona_package_store import FullPersonaPackageStore
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona_pack import PersonaLayer, PersonaPack
from ynoy.models.persona_dossier import DOSSIER_TOPIC_ORDER
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.util import canonical_sha256, utc_now


def _persisted_package(
    tmp_path: Path,
) -> tuple[Path, str, PersonaPack, FullPersonaPackageStore, Path]:
    _source_root, private_root, manifest, pack = built_pack(tmp_path)
    FullPersonaPackStore(private_root, synthetic=True).write_pack(pack)
    package = build_full_persona_package(pack)
    store = FullPersonaPackageStore(private_root, synthetic=True)
    path = store.write_package(package)
    assert manifest.run_id == pack.source_run_id
    return private_root, pack.source_run_id, pack, store, path


def test_build_full_persona_package_is_deterministic_and_canonical(tmp_path: Path) -> None:
    _source_root, _private_root, _manifest, pack = built_pack(tmp_path)

    first = build_full_persona_package(pack)
    second = build_full_persona_package(pack)

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.package_id == canonical_sha256(
        {
            "protocol_version": first.protocol_version,
            "pack_sha256": first.pack_sha256,
            "dossier_sha256": first.dossier.dossier_sha256,
            "evolution_sha256": first.evolution.evolution_sha256,
        }
    )
    assert first.package_sha256 == canonical_sha256(
        first.model_dump(mode="json", exclude={"package_sha256"})
    )


def test_package_contains_all_topics_and_explicit_unknown_biography_topics(
    tmp_path: Path,
) -> None:
    pack = _plain_pack(tmp_path)

    package = build_full_persona_package(pack)
    topics = {topic.key: topic for topic in package.dossier.topics}

    assert tuple(topics) == DOSSIER_TOPIC_ORDER
    assert len(topics) == 14
    for key in ("birth", "childhood", "education", "exams"):
        assert topics[key].evidence_state == "unknown"
        assert f"{key}_not_established_by_literal_direct_evidence" in topics[key].unknowns


def test_layer_counts_reconcile_and_duplicate_observations_are_accounted_for(
    tmp_path: Path,
) -> None:
    _source_root, _private_root, _manifest, pack = built_pack(tmp_path)
    package = build_full_persona_package(pack)

    assert sum(item.retained_atom_count for item in package.layer_summaries) == (
        package.retained_atom_count
    )
    assert sum(item.unique_semantic_claim_count for item in package.layer_summaries) == (
        package.unique_semantic_claim_count
    )
    for item in package.layer_summaries:
        assert item.duplicate_observation_count == max(
            0, item.represented_observation_count - item.unique_semantic_claim_count
        )

    duplicate_pack = _with_observation_count(pack, PersonaLayer.EVIDENCE, 3)
    duplicate_package = build_full_persona_package(duplicate_pack)
    evidence = next(
        item for item in duplicate_package.layer_summaries if item.layer == PersonaLayer.EVIDENCE
    )
    assert evidence.unique_semantic_claim_count == 17
    assert evidence.represented_observation_count == 19
    assert evidence.duplicate_observation_count == 2


def test_package_store_roundtrip_and_tamper_failure(tmp_path: Path) -> None:
    _private_root, run_id, _pack, store, path = _persisted_package(tmp_path)
    package_id = path.name.removesuffix(".persona-package.json")

    assert store.read_package(run_id) == store.read_package(run_id, package_id)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["retained_atom_count"] += 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DataValidationError) as error:
        store.read_package(run_id, package_id)
    assert error.value.code == "persona_package_invalid"


def test_brain_atlas_is_deterministic_receipt_bound_and_private(tmp_path: Path) -> None:
    _private_root, _run_id, pack, store, _path = _persisted_package(tmp_path)
    package = build_full_persona_package(pack)
    first = render_persona_brain_atlas(package)
    second = render_persona_brain_atlas(package)

    atlas_path = store.write_brain_atlas(package, first)
    assert first == second == atlas_path.read_text(encoding="utf-8")
    assert "# Full Persona Brain Atlas" in first
    assert "## Evolution" in first
    assert "- Use: proposal_context_only" in first
    assert "- Receipt:" in first
    assert "Persona quality: not claimed" in first


def test_package_store_rejects_stale_latest_pointer(tmp_path: Path) -> None:
    _private_root, run_id, _pack, store, path = _persisted_package(tmp_path)
    pointer = path.parent / "latest-persona-package.json"
    pointer.write_text(
        json.dumps(
            {
                "package_id": path.name.removesuffix(".persona-package.json"),
                "package_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as error:
        store.read_package(run_id)
    assert error.value.code == "persona_package_store_invalid"


def test_cli_package_summary_does_not_emit_private_paths(tmp_path: Path) -> None:
    private_root, run_id, _pack, _store, _path = _persisted_package(tmp_path)
    context = CommandContext(
        settings=Settings.from_environment(private_root=private_root),
        repository_root=tmp_path,
    )

    result = build_full_persona_package_handler(
        parse_args(["study", "build-full-persona-package", run_id, "--synthetic"]),
        context,
    )

    assert result["status"] == "full_persona_package_built"
    assert result["brain_atlas_built"] is True
    assert result["private_path_emitted"] is False
    assert result["private_content_emitted"] is False
    assert result["evolution_status"] == "derived_unadopted"
    assert result["evolution_use"] == "proposal_context_only"
    assert _strings(result).isdisjoint({str(private_root), str(private_root.resolve())})


def test_full_persona_deletion_removes_package_closure(tmp_path: Path) -> None:
    _private_root, run_id, _pack, _store, package_path = _persisted_package(tmp_path)

    deleted = delete_full_persona_run(_private_root, run_id, synthetic=True)

    assert deleted > 0
    assert not package_path.exists()
    assert not package_path.parent.exists()


def _with_observation_count(pack: PersonaPack, layer: PersonaLayer, count: int) -> PersonaPack:
    payload = pack.model_dump(mode="json")
    layers = payload["layers"]
    selected = next(item for item in layers if item["layer"] == layer.value)
    atom = selected["atoms"][0]
    atom["observation_count"] = count
    atom["atom_id"] = canonical_sha256(
        {key: value for key, value in atom.items() if key != "atom_id"}
    )
    selected["atoms"] = sorted(selected["atoms"], key=lambda item: item["atom_id"])
    payload["pack_sha256"] = canonical_sha256(
        {key: value for key, value in payload.items() if key != "pack_sha256"}
    )
    return PersonaPack.model_validate(payload)


def _plain_pack(tmp_path: Path) -> PersonaPack:
    source_root, _ = synthetic_codex_study_root(tmp_path)
    private_root = tmp_path / "private"
    study = prepare_persona_study(
        source_root, private_root, synthetic=True, evaluation_time=utc_now()
    )
    manifest = freeze_full_corpus(
        source_root, private_root, study.manifest.study_id, synthetic=True
    )
    FullPersonaStore(private_root, synthetic=True).write_manifest(manifest)
    scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    return build_deterministic_pack(private_root, manifest.run_id, synthetic=True)


def _strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return {item for child in value.values() for item in _strings(child)}
    if isinstance(value, (tuple, list)):
        return {item for child in value for item in _strings(child)}
    return set()
