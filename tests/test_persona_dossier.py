# ruff: noqa: RUF001 -- Turkish synthetic evidence is intentional.

from __future__ import annotations

from pathlib import Path

from support.persona_pack import built_pack, pack_atoms
from support.persona_study import synthetic_codex_study_root

from ynoy.full_persona.dossier import build_persona_dossier
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.util import utc_now

TOPIC_KEYS = (
    "birth",
    "childhood",
    "education",
    "exams",
    "work_projects",
    "knowledge",
    "skills",
    "values",
    "goals",
    "decision_behavior",
    "risk_boundaries",
    "relationships",
    "contradictions",
    "response_style",
)


def _topic_key(topic: object) -> str:
    value = topic.key  # type: ignore[attr-defined]
    return str(getattr(value, "value", value))


def _plain_pack(tmp_path: Path):
    source, _ = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    study = prepare_persona_study(source, private, synthetic=True, evaluation_time=utc_now())
    manifest = freeze_full_corpus(source, private, study.manifest.study_id, synthetic=True)
    store = FullPersonaStore(private, synthetic=True)
    store.write_manifest(manifest)
    scan_full_corpus(source, private, manifest.run_id, synthetic=True)
    return build_deterministic_pack(private, manifest.run_id, synthetic=True)


def _topics(dossier: object) -> dict[str, object]:
    return {_topic_key(item): item for item in dossier.topics}


def test_dossier_has_ordered_lifecycle_topics_and_private_bindings(tmp_path: Path) -> None:
    pack = _plain_pack(tmp_path)
    dossier = build_persona_dossier(pack)

    assert tuple(_topic_key(item) for item in dossier.topics) == TOPIC_KEYS
    assert dossier.pack_id == pack.pack_id
    assert dossier.source_run_id == pack.source_run_id
    assert dossier.source_manifest_sha256 == pack.source_manifest_sha256
    assert dossier.source_head_sha256 == pack.source_head_sha256
    assert dossier.source_head_revision == pack.source_head_revision
    assert dossier.dossier_sha256
    assert dossier.persistent is False
    assert dossier.persona_quality_claimed is False
    assert dossier.calibration_status == "not_calibrated"
    assert dossier.authority == "none"


def test_dossier_marks_absent_biography_and_exams_unknown_without_invention(
    tmp_path: Path,
) -> None:
    topics = _topics(build_persona_dossier(_plain_pack(tmp_path)))

    for key in ("birth", "childhood", "exams", "relationships"):
        topic = topics[key]
        assert topic.candidates == ()
        assert topic.unknowns
    assert all(
        "1990" not in unknown and "anne" not in unknown.lower()
        for topic in (topics["birth"], topics["childhood"], topics["exams"])
        for unknown in topic.unknowns
    )


def test_dossier_candidates_are_direct_literal_unadopted_and_bound_to_pack(
    tmp_path: Path,
) -> None:
    _, _, _, pack = built_pack(tmp_path)
    atom_ids = {atom.atom_id for atom in pack_atoms(pack)}
    dossier = build_persona_dossier(pack)
    candidates = [candidate for topic in dossier.topics for candidate in topic.candidates]

    assert candidates
    assert all(candidate.atom_id in atom_ids for candidate in candidates)
    assert all(candidate.source_role == "direct_user_expression" for candidate in candidates)
    assert all(candidate.evidence_receipts for candidate in candidates)
    assert all(
        candidate.evidence_receipt_count >= len(candidate.evidence_receipts)
        for candidate in candidates
    )
    assert all(candidate.adopted is False for candidate in candidates)
    assert all(candidate.core_eligible is False for candidate in candidates)
    assert all(candidate.semantic_adoption == "not_established" for candidate in candidates)


def test_response_style_is_derived_unadopted_and_has_two_supports_per_signal(
    tmp_path: Path,
) -> None:
    dossier = build_persona_dossier(built_pack(tmp_path)[3])
    response_style = _topics(dossier)["response_style"]

    assert response_style.candidates == ()
    assert response_style.evidence_state in {"derived_unadopted", "unknown"}
    for signal in response_style.style_signals:
        assert signal.status == "derived_unadopted"
        assert signal.authority == "none"
        assert len(signal.supports) == 2
        assert all(item.atom_id for item in signal.supports)
        assert all(item.evidence_receipts for item in signal.supports)


def test_project_instruction_role_is_excluded_from_dossier_candidates(tmp_path: Path) -> None:
    _, _, _, pack = built_pack(tmp_path)
    dossier = build_persona_dossier(pack)
    claims = [candidate.claim.lower() for topic in dossier.topics for candidate in topic.candidates]

    assert all("proje kuralı" not in claim for claim in claims)
    assert all("please implement this plan" not in claim for claim in claims)


def test_dossier_build_is_deterministic_and_does_not_emit_paths_or_raw_source(
    tmp_path: Path,
) -> None:
    pack = _plain_pack(tmp_path)
    first = build_persona_dossier(pack)
    second = build_persona_dossier(pack)

    assert first == second
    assert first.dossier_sha256 == second.dossier_sha256
    encoded = first.model_dump_json()
    assert str(tmp_path) not in encoded
    assert "raw-private-thread" not in encoded
