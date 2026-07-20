from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from support.reaction_baseline import assert_static_predictions_safe

from ynoy.errors import DataValidationError
from ynoy.full_persona.reaction_baselines import (
    REACTION_ARMS,
    run_reaction_baselines,
)
from ynoy.full_persona.reaction_split import build_reaction_split
from ynoy.models.base import DataClass
from ynoy.models.full_persona import (
    EvidenceRole,
    FullCorpusContext,
    FullCorpusEvidence,
    FullCorpusLimits,
    FullCorpusManifest,
)
from ynoy.models.full_persona_source import FullCorpusSource
from ynoy.models.persona_reaction_benchmark import (
    REACTION_SIGNALS,
    PersonaReactionManifest,
    PersonaReactionTargetSeal,
)
from ynoy.util import canonical_sha256, sha256_text

_START = datetime(2026, 1, 1, tzinfo=UTC)
_SIGNALS = tuple(REACTION_SIGNALS)
_BASELINE_ARMS = (
    "history_majority",
    "chronological_recency",
    "lexical_retrieval",
    "static_profile",
)


def _arm_map(run):
    if hasattr(run, "arms"):
        return run.arms
    return {item.arm: item.predictions for item in run}


def _run(split):
    return run_reaction_baselines(
        split.manifest,
        split.history,
        split.cases,
        expected_manifest_sha256=split.manifest.manifest_sha256,
    )


def _evidence(index: int, *, development: bool) -> FullCorpusEvidence:
    cluster = index % 8 if development else 8 + (index % 8)
    moment = _START + timedelta(days=index if development else 100 + index)
    content = f"synthetic user decision {index} {('approve' if index % 2 else 'reject')}"
    context_text = (
        f"sealed novelterm {index}"
        if not development and index == 16
        else f"preceding context for case {index}"
    )
    source = sha256_text(f"source-{cluster}")
    conversation = sha256_text(f"conversation-{cluster}")
    turn = sha256_text(f"turn-{index}")
    source_payload = _source_payload(cluster)
    payload = {
        "evidence_id": sha256_text(f"evidence-{index}"),
        "source_key": source,
        "source_receipt": source_payload["source_receipt"],
        "blob_sha256": sha256_text(f"blob-{cluster}"),
        "byte_start": index * 100,
        "byte_length": len(content.encode()),
        "line_number": index + 1,
        "record_sha256": sha256_text(f"record-{index}"),
        "conversation_key": conversation,
        "turn_key": turn,
        "event_time": moment,
        "time_basis": "event",
        "role": EvidenceRole.DIRECT,
        "signal_tags": ("decision" if development and index < 12 else "correction",),
        "context": (
            FullCorpusContext(
                speaker="user",
                content=context_text,
                content_sha256=sha256_text(context_text),
            ),
        ),
        "content": content,
        "content_sha256": sha256_text(content),
    }
    draft = FullCorpusEvidence.model_construct(**payload, evidence_sha256="0" * 64)
    return FullCorpusEvidence.model_validate(
        {
            **draft.model_dump(mode="json"),
            "evidence_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"evidence_sha256"})
            ),
        }
    )


def _source_payload(index: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "partition": "sessions",
        "relative_locator": f"synthetic/source-{index}.jsonl",
        "source_key": sha256_text(f"source-{index}"),
        "file_bytes": 65_536,
        "modified_ns": 1_700_000_000_000_000_000 + index,
        "device": 1,
        "inode": index + 1,
        "session_start_ns": 1_700_000_000_000_000_000 + index,
        "thread_receipt": sha256_text(f"thread-{index}"),
        "lineage_component_receipt": sha256_text(f"lineage-{index}"),
        "blob_sha256": sha256_text(f"blob-{index}"),
        "chunk_size_bytes": 65_536,
        "chunk_sha256": (sha256_text(f"chunk-{index}"),),
        "parent_thread_receipt": None,
    }
    draft = FullCorpusSource.model_construct(**payload, source_receipt="0" * 64)
    canonical = draft.model_dump(mode="json", exclude={"source_receipt"})
    return {**canonical, "source_receipt": canonical_sha256(canonical)}


def _source_manifest() -> FullCorpusManifest:
    sources = tuple(FullCorpusSource.model_validate(_source_payload(index)) for index in range(16))
    payload = {
        "run_id": sha256_text("reaction-run"),
        "source_study_id": sha256_text("reaction-study"),
        "holdout_freeze_sha256": sha256_text("holdout"),
        "holdout_boundary_session_start_ns": 1_800_000_000_000_000_000,
        "stable_before_ns": 1_700_000_000_000_000_100,
        "created_at": _START,
        "expires_at": _START + timedelta(days=30),
        "limits": FullCorpusLimits(max_manifest_files=100_000),
        "source_data_class": DataClass.PUBLIC_SYNTHETIC,
        "synthetic": True,
        "files": sources,
        "expected_file_count": 16,
        "expected_input_bytes": 16 * 65_536,
        "source_snapshot_sha256": canonical_sha256(
            [item.model_dump(mode="json") for item in sources]
        ),
        "excluded_files": (),
        "expected_excluded_file_count": 0,
        "exclusion_snapshot_sha256": canonical_sha256([]),
    }
    draft = FullCorpusManifest.model_construct(**payload, manifest_sha256="0" * 64)
    payload["manifest_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"manifest_sha256"})
    )
    return FullCorpusManifest.model_validate(payload)


def _dataset() -> tuple[FullCorpusManifest, tuple[FullCorpusEvidence, ...]]:
    return _source_manifest(), tuple(_evidence(i, development=i < 16) for i in range(40))


def _split():
    manifest, evidence = _dataset()
    return build_reaction_split(
        manifest,
        evidence,
        sealed_count=24,
    )


def test_split_has_exact_sealed_size_and_target_free_cases() -> None:
    split = _split()
    assert len(split.cases) == 24
    assert len(split.history) == 16
    assert max(item.event_time for item in split.history) < split.manifest.temporal_cutoff
    assert split.manifest.temporal_cutoff < min(item.event_time for item in split.cases)
    assert len({item.conversation_key for item in split.cases}) >= 8
    assert len({item.source_key for item in split.cases}) >= 8
    assert {item.source_key for item in split.history}.isdisjoint(
        {item.source_key for item in split.cases}
    )
    assert {item.conversation_key for item in split.history}.isdisjoint(
        {item.conversation_key for item in split.cases}
    )
    assert {item.lineage_component_receipt for item in split.history}.isdisjoint(
        {item.lineage_component_receipt for item in split.cases}
    )
    assert tuple(item.case_id for item in split.cases) == split.manifest.sealed_case_ids
    for case in split.cases:
        dumped = case.model_dump(mode="json")
        assert case.context
        assert not any(key in dumped for key in ("label", "signal_tags", "target_text", "content"))
    for payload in (
        split.manifest.model_dump(mode="json"),
        split.target_seal.model_dump(mode="json"),
    ):
        assert not any(key in payload for key in ("label", "signal_tags", "target_text", "content"))


def test_split_rejects_leakage_and_invalid_signal() -> None:
    manifest, evidence = _dataset()
    changed = list(evidence)
    changed[20] = changed[20].model_copy(update={"signal_tags": ("unknown_signal",)})
    with pytest.raises((DataValidationError, ValueError)):
        build_reaction_split(manifest, changed, sealed_count=24)

    changed = list(evidence)
    changed[20] = changed[20].model_copy(update={"event_time": _START})
    with pytest.raises((DataValidationError, ValueError)):
        build_reaction_split(manifest, changed, sealed_count=24)


def test_split_hashes_are_disjoint_and_receipts_are_tamper_evident() -> None:
    split = _split()
    assert split.manifest.manifest_sha256 == canonical_sha256(
        split.manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    )
    locators = split.target_seal.locators
    first_locator = next(iter(locators.values())) if isinstance(locators, dict) else locators[0]
    assert first_locator.locator_sha256 == canonical_sha256(
        first_locator.model_dump(mode="json", exclude={"locator_sha256"})
    )
    with pytest.raises(ValueError):
        PersonaReactionManifest.model_validate(
            split.manifest.model_dump(mode="python") | {"manifest_sha256": "0" * 64}
        )
    with pytest.raises(ValueError):
        PersonaReactionTargetSeal.model_validate(
            split.target_seal.model_dump(mode="python") | {"seal_sha256": "0" * 64}
        )
    assert split.target_seal.seal_sha256 == canonical_sha256(
        split.target_seal.model_dump(mode="json", exclude={"seal_sha256"})
    )


def test_split_and_baselines_are_deterministic_and_keep_six_arms() -> None:
    first = _split()
    second = _split()
    assert first.manifest == second.manifest
    assert tuple(item.case_id for item in first.sealed_cases) == tuple(
        item.case_id for item in second.sealed_cases
    )
    first_run = _run(first)
    second_run = _run(second)
    assert first_run == second_run
    assert first.manifest.arms == REACTION_ARMS
    assert tuple(_arm_map(first_run)) == _BASELINE_ARMS
    assert tuple(REACTION_ARMS) == (
        "generic_local_8b",
        *_BASELINE_ARMS,
        "structured_persona",
    )
    case_orders = {
        tuple(item.case_id for item in predictions) for predictions in _arm_map(first_run).values()
    }
    assert case_orders == {first.manifest.sealed_case_ids}


def test_baselines_use_development_only_and_never_persona_pack() -> None:
    split = _split()
    run = _run(split)
    for arm, predictions in _arm_map(run).items():
        assert arm in _BASELINE_ARMS
        assert all(item.persona_identity is False for item in predictions)
        assert all(item.calibration_used is False for item in predictions)
        assert all(item.semantic_adoption is False for item in predictions)
        assert all(item.core_eligible is False for item in predictions)
        for prediction in predictions:
            assert prediction.target_seen is False
            assert prediction.target_text is None
            assert prediction.case_id in split.manifest.sealed_case_ids
            assert set(prediction.evidence_ids).issubset(
                {item.evidence_id for item in split.history}
            )
    lexical = _arm_map(run)["lexical_retrieval"]
    assert any(item.abstained for item in lexical)
    assert all(item.case_id not in item.model_dump(mode="json") for item in lexical)


def test_baseline_semantics_majority_recency_retrieval_and_static_profile() -> None:
    split = _split()
    run = _run(split)
    arms = _arm_map(run)
    majority = arms["history_majority"]
    recency = arms["chronological_recency"]
    lexical = arms["lexical_retrieval"]
    static = arms["static_profile"]
    assert majority[0].predicted_label == "decision"
    assert recency[0].predicted_label == "correction"
    assert recency[0].evidence_ids
    assert set(recency[0].evidence_ids).issubset({item.evidence_id for item in split.history})
    assert any(item.abstained and item.evidence_ids == () for item in lexical)
    assert_static_predictions_safe(static, split)


def test_current_full_persona_pack_is_not_a_reaction_input() -> None:
    manifest, _ = _dataset()
    with pytest.raises((TypeError, DataValidationError, ValueError)):
        build_reaction_split(manifest, object(), sealed_count=24)
