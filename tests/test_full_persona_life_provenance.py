# ruff: noqa: RUF001 -- Turkish identity evidence is intentional.

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from support.full_persona import canonical_file
from support.persona_study import synthetic_codex_study_root

from ynoy.full_persona.life_profile import build_verified_life_profile
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.persona_life_profile import PersonaLifeCandidate, PersonaLifeProfile
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.util import utc_now


def _append_fact(path: Path, *, day: int, minute: int) -> None:
    payload = {
        "type": "response_item",
        "timestamp": f"2026-01-{day:02d}T03:{minute:02d}:00+00:00",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Şu anda 32 yaşındayım."}],
        },
    }
    original_mtime = path.stat().st_mtime_ns
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.utime(path, ns=(original_mtime, original_mtime))


def _built_repeated_fact(tmp_path: Path):
    source_root, _ = synthetic_codex_study_root(tmp_path)
    _append_fact(canonical_file(source_root, 0), day=1, minute=20)
    _append_fact(canonical_file(source_root, 2), day=3, minute=21)
    private_root = tmp_path / "private"
    prepared = prepare_persona_study(
        source_root,
        private_root,
        synthetic=True,
        evaluation_time=utc_now(),
    )
    manifest = freeze_full_corpus(
        source_root,
        private_root,
        prepared.manifest.study_id,
        synthetic=True,
    )
    corpus = FullPersonaStore(private_root, synthetic=True)
    corpus.write_manifest(manifest)
    head = scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    assert head.status == "complete"
    profile = build_verified_life_profile(corpus, manifest, head)
    return profile


def test_repeated_life_fact_retains_distinct_source_supports(tmp_path: Path) -> None:
    profile = _built_repeated_fact(tmp_path)
    topic = next(item for item in profile.topics if item.key == "current_life")
    candidate = next(item for item in topic.candidates if "32 yaşındayım" in item.claim)

    assert candidate.support_count == 2
    assert candidate.support_projection_exhaustive is True
    assert len(candidate.supports) == 2
    assert len({item.evidence_id for item in candidate.supports}) == 2
    assert len({item.source_receipt for item in candidate.supports}) == 2
    assert tuple(item.evidence_id for item in candidate.supports) == tuple(
        sorted(item.evidence_id for item in candidate.supports)
    )


def test_life_candidate_rejects_missing_support_and_profile_rejects_tampering(
    tmp_path: Path,
) -> None:
    profile = _built_repeated_fact(tmp_path)
    topic_index, topic = next(
        (index, item) for index, item in enumerate(profile.topics) if item.key == "current_life"
    )
    candidate = next(item for item in topic.candidates if "32 yaşındayım" in item.claim)

    missing_support = candidate.model_dump(mode="python")
    missing_support["supports"] = missing_support["supports"][:1]
    with pytest.raises(ValueError):
        PersonaLifeCandidate.model_validate(missing_support)

    tampered_candidate = candidate.model_dump(mode="python")
    tampered_support = dict(tampered_candidate["supports"][0])
    tampered_support["evidence_sha256"] = "0" * 64
    tampered_candidate["supports"] = [tampered_support, *tampered_candidate["supports"][1:]]
    tampered_topic = topic.model_dump(mode="python")
    tampered_topic["candidates"] = [tampered_candidate, *tampered_topic["candidates"][1:]]
    payload = profile.model_dump(mode="python")
    topics = list(payload["topics"])
    topics[topic_index] = tampered_topic
    payload["topics"] = topics
    with pytest.raises(ValueError):
        PersonaLifeProfile.model_validate(payload)
