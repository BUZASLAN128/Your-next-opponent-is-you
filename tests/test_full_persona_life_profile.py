# ruff: noqa: RUF001 -- Turkish identity evidence is intentional.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.life_profile import (
    LIFE_PROFILE_EVIDENCE,
    LIFE_PROFILE_EXPECTED_FACTS,
    LIFE_PROFILE_FALSE_POSITIVES,
    prepared_life_profile_source,
)

from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.full_persona.deletion import delete_full_persona_run
from ynoy.full_persona.identity_rules import has_relationship_claim, has_skill_claim
from ynoy.full_persona.life_profile import build_verified_life_profile
from ynoy.full_persona.life_profile_store import FullPersonaLifeProfileStore
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import EvidenceRole


def _built_profile(tmp_path: Path, *, include_life_evidence: bool = True):
    source_root, private_root, _prepared, run_id = prepared_life_profile_source(
        tmp_path,
        include_life_evidence=include_life_evidence,
    )
    corpus = FullPersonaStore(private_root, synthetic=True)
    manifest = corpus.read_manifest(run_id)
    head = corpus.read_head(run_id)
    profile = build_verified_life_profile(corpus, manifest, head)
    return source_root, private_root, run_id, corpus, manifest, head, profile


def test_life_profile_scans_all_evidence_and_covers_each_topic(tmp_path: Path) -> None:
    _source, _private, _run_id, _corpus, _manifest, head, profile = _built_profile(tmp_path)

    assert profile.scanned_evidence_count == head.evidence_count
    assert profile.scanned_evidence_count > len(LIFE_PROFILE_EVIDENCE)
    assert tuple(topic.key for topic in profile.topics) == (
        "birth",
        "childhood",
        "education",
        "exams",
        "current_life",
    )
    assert all(topic.candidates for topic in profile.topics)
    assert all(
        topic.unknowns == ("current_meaning_and_adoption_unreviewed",) for topic in profile.topics
    )


def test_life_profile_marks_unestablished_topics_with_explicit_unknowns(tmp_path: Path) -> None:
    _source, _private, _run_id, _corpus, _manifest, _head, profile = _built_profile(
        tmp_path,
        include_life_evidence=False,
    )

    assert all(topic.evidence_state == "unknown" for topic in profile.topics)
    assert all(
        topic.unknowns == (f"{topic.key}_not_established_by_literal_direct_evidence",)
        for topic in profile.topics
    )


def test_life_profile_rejects_vocatives_generic_exam_and_ide_context(tmp_path: Path) -> None:
    _source, _private, _run_id, _corpus, _manifest, _head, profile = _built_profile(tmp_path)
    claims = "\n".join(
        candidate.claim for topic in profile.topics for candidate in topic.candidates
    )

    for expected in LIFE_PROFILE_EXPECTED_FACTS:
        assert expected in claims
    for rejected in LIFE_PROFILE_FALSE_POSITIVES:
        assert rejected not in claims
    assert all(
        candidate.source_role == "direct_user_expression"
        for topic in profile.topics
        for candidate in topic.candidates
    )


def test_identity_rules_and_evidence_roles_keep_weak_signals_out(tmp_path: Path) -> None:
    _source, _private, _run_id, corpus, manifest, head, _profile = _built_profile(tmp_path)
    evidence = tuple(iter_verified_evidence(corpus, manifest, head))
    ide = next(item for item in evidence if "context from my IDE setup" in item.content)

    assert not has_relationship_claim("Oğlum, bugün hava güzel.")
    assert not has_relationship_claim("Arkadaşım, yarın görüşürüz.")
    assert has_relationship_claim("Bir arkadaşımla beraber çalışıyorum.")
    assert not has_skill_claim("Yapabiliyorum.")
    assert has_skill_claim("Yıllardır Python kullanıyorum.")
    assert ide.role == EvidenceRole.MIXED


def test_life_profile_hash_is_deterministic_for_same_verified_run(tmp_path: Path) -> None:
    _source, _private, _run_id, corpus, manifest, head, first = _built_profile(tmp_path)

    second = build_verified_life_profile(corpus, manifest, head)

    assert second.profile_id == first.profile_id
    assert second.profile_sha256 == first.profile_sha256
    assert second.model_dump(mode="json") == first.model_dump(mode="json")


def test_private_life_profile_store_roundtrips_and_rejects_tampering(tmp_path: Path) -> None:
    _source, private_root, run_id, _corpus, _manifest, _head, profile = _built_profile(tmp_path)
    store = FullPersonaLifeProfileStore(private_root, synthetic=True)

    path = store.write(profile)
    assert store.read(run_id) == profile
    path.write_bytes(
        path.read_bytes().replace(b'"semantic_exhaustive":false', b'"semantic_exhaustive":true')
    )

    with pytest.raises(DataValidationError) as error:
        store.read(run_id)
    assert error.value.code == "life_profile_invalid"


def test_life_profile_cli_emits_status_without_private_paths_or_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _source, _private, run_id, _corpus, _manifest, _head, _profile = _built_profile(tmp_path)

    exit_code = main(
        [
            "--private-root",
            str(tmp_path / "private"),
            "study",
            "build-full-persona-life-profile",
            run_id,
            "--synthetic",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert str(tmp_path) not in output
    assert "02-01-1990 tarihinde doğdum" not in output
    result = json.loads(output)["result"]
    assert result["status"] == "full_persona_life_profile_built"
    assert result["private_content_emitted"] is False


def test_full_persona_deletion_removes_life_profile_closure(tmp_path: Path) -> None:
    _source, private_root, run_id, _corpus, _manifest, _head, profile = _built_profile(tmp_path)
    profile_store = FullPersonaLifeProfileStore(private_root, synthetic=True)
    profile_path = profile_store.write(profile)
    pack_run = profile_path.parents[1]
    assert profile_path.is_file()

    deleted = delete_full_persona_run(private_root, run_id, synthetic=True)

    assert deleted > 0
    assert not profile_path.exists()
    assert not pack_run.exists()
    assert not FullPersonaStore(private_root, synthetic=True).run_path(run_id).exists()
