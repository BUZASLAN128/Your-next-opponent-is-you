# ruff: noqa: RUF001 -- Turkish judgment fixtures mirror the selector vocabulary.

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from support.harvest import normalized_event, sealed_candidate

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.models import ClaimHolder, SourceAuthority
from ynoy.models.persona_harvest import HarvestLimits
from ynoy.persona_study.harvest_contract import seal_harvest_candidate, seal_harvest_manifest
from ynoy.persona_study.harvest_events import HarvestContextBuffer, offer_harvest_event
from ynoy.persona_study.harvest_reservoir import HarvestReservoir
from ynoy.persona_study.harvest_signals import evaluate_harvest_event
from ynoy.util import sha256_text


def _limits(**changes: int) -> HarvestLimits:
    values = dict(changes)
    context_bytes = int(values.pop("max_context_bytes", 2_000))
    return HarvestLimits(
        max_total_input_bytes=10_000,
        max_file_bytes=10_000,
        max_line_bytes=8_000,
        max_focus_bytes=2_000,
        max_context_bytes=context_bytes,
        max_artifact_bytes=20_000,
        **values,
    )


def _manifest(limits: HarvestLimits | None = None):
    now = datetime(2026, 2, 1, tzinfo=UTC)
    return seal_harvest_manifest(
        run_id="1" * 64,
        source_study_id="2" * 64,
        freeze_sha256="3" * 64,
        boundary_ns=int((now + timedelta(days=1)).timestamp() * 1_000_000_000),
        stable_before_ns=int(now.timestamp() * 1_000_000_000),
        limits=limits or _limits(),
        created_at=now,
        expires_at=now + timedelta(days=1),
        synthetic=True,
    )


@pytest.mark.parametrize(
    ("text", "tag"),
    [
        ("Bu kararı onaylıyorum, devam et.", "decision"),
        ("Yanlış, bunu düzelt ve tekrar test et.", "correction"),
        ("Bunun için kanıt ve test sonucu göster.", "evidence_demand"),
        ("Şimdilik yalnız bu proje kapsamına al.", "scope_change"),
        ("Emin değilim, şimdilik ertele.", "abstention"),
        ("Bu düzeltme çalışmadı, hata verdi.", "outcome_feedback"),
    ],
)
def test_structural_user_judgment_signals_are_scored(text: str, tag: str) -> None:
    result = evaluate_harvest_event(normalized_event("user", text), _limits())

    assert result.exclusion is None
    assert tag in result.tags
    assert result.score >= 1


@pytest.mark.parametrize(
    "text", ["Merhaba, bugün hava nasıl?", "Write Hello World to f:/cerberus-repos/.swarm/test.txt"]
)
def test_unrelated_user_turn_is_excluded_without_signal(text: str) -> None:
    result = evaluate_harvest_event(normalized_event("user", text), _limits())

    assert result.tags == ()
    assert result.score == 0
    assert result.exclusion == "no_judgment_signal"


@pytest.mark.parametrize("role", ["assistant", "system", "developer", "tool"])
def test_non_user_roles_never_become_harvest_candidates(role: str) -> None:
    result = evaluate_harvest_event(
        normalized_event(role, "Onaylıyorum, bunu uygula ve test et."), _limits()
    )

    assert result.tags == ()
    assert result.exclusion in {"non_user_origin", "non_dialogue", "control_or_tool_content"}


@pytest.mark.parametrize(
    "text",
    [
        "```python\nOnaylıyorum; bunu uygula.\n```",
        "> Alıntı: bunu kesinlikle kabul et.",
        "# Files mentioned by the user:\nOnaylıyorum",
        "<subagent_notification>Onaylıyorum</subagent_notification>",
    ],
)
def test_imported_quoted_pasted_and_subagent_text_is_excluded(text: str) -> None:
    event = normalized_event("user", text)
    result = evaluate_harvest_event(event, _limits())

    assert result.exclusion in {
        "quoted_or_imported_content",
        "non_user_origin",
        "no_judgment_signal",
        "subagent_or_delegation",
    }
    assert result.tags == ()


def test_quoted_prefix_with_judgment_signal_is_excluded() -> None:
    result = evaluate_harvest_event(
        normalized_event("user", "> Alıntı: bunu onaylıyorum, uygula ve test et."), _limits()
    )

    assert result.exclusion == "quoted_or_imported_content"
    assert result.tags == ()


def test_ide_context_wrapper_with_judgment_signal_is_excluded() -> None:
    result = evaluate_harvest_event(
        normalized_event(
            "user", "# Context from my IDE setup:\nOnaylıyorum, bunu uygula ve test et."
        ),
        _limits(),
    )

    assert result.exclusion == "quoted_or_imported_content"
    assert result.tags == ()


def test_aborted_turn_with_judgment_signal_is_imported_content() -> None:
    result = evaluate_harvest_event(
        normalized_event(
            "user",
            "<turn_aborted>Onaylıyorum, bunu uygula ve test et.</turn_aborted>",
        ),
        _limits(),
    )

    assert result.exclusion == "quoted_or_imported_content"
    assert result.tags == ()


@pytest.mark.parametrize(
    "text",
    ["Düzelt.", "Kalsın."],
    ids=["short-correction", "short-decision"],
)
def test_short_correction_and_decision_signals_remain_eligible(text: str) -> None:
    result = evaluate_harvest_event(normalized_event("user", text), _limits())

    assert result.exclusion is None
    assert result.score >= 1


def test_short_evidence_only_operational_fragment_is_excluded() -> None:
    result = evaluate_harvest_event(normalized_event("user", "Test sonucu göster."), _limits())

    assert result.exclusion == "low_signal_short_focus"


@pytest.mark.parametrize("text", ["test ettin mi", "test sonucu göster"])
def test_short_evidence_requests_use_the_quality_gate(text: str) -> None:
    result = evaluate_harvest_event(normalized_event("user", text), _limits())

    assert result.tags == ()
    assert result.score == 0
    assert result.exclusion == "low_signal_short_focus"


def test_focus_matching_context_user_hash_is_duplicate_excluded() -> None:
    manifest = _manifest()
    context = HarvestContextBuffer(manifest)
    content = "Bunu onaylıyorum, uygula ve test et."
    context.observe(normalized_event("user", content))
    exclusions: Counter[str] = Counter()
    reservoir = HarvestReservoir(3, manifest.selector_config_sha256)
    item = DiscoveredCodexFile(
        partition="sessions",
        path=Path("synthetic.jsonl"),
        relative=Path("2026/01/02/synthetic.jsonl"),
        file_bytes=100,
        modified_ns=1,
        device=0,
        inode=0,
    )

    offer_harvest_event(
        reservoir,
        exclusions,
        normalized_event("user", content),
        item,
        "a" * 64,
        context,
        manifest,
    )

    assert exclusions["duplicate_representation"] == 1
    assert reservoir.candidates == ()


def test_non_unknown_claim_holder_is_excluded() -> None:
    event = normalized_event("user", "Bunu onaylıyorum, test et.").model_copy(
        update={"claim_holder": ClaimHolder.THIRD_PARTY}
    )
    result = evaluate_harvest_event(event, _limits())

    assert result.exclusion == "claim_holder_not_unknown"


def test_user_candidate_must_remain_unattributed() -> None:
    event = normalized_event("user", "Bunu onaylıyorum, test et.").model_copy(
        update={"source_authority": SourceAuthority.EXPLICIT_USER_STATEMENT}
    )
    result = evaluate_harvest_event(event, _limits())

    assert result.exclusion == "user_authority_not_unattributed"


def test_reservoir_is_order_independent_and_bounded() -> None:
    manifest = _manifest(_limits(max_reservoir=3))
    events = [
        normalized_event("user", text)
        for text in (
            "Bunu onaylıyorum, test et.",
            "Yanlış, düzelt ve kanıt göster.",
            "Şimdilik bu kapsamla devam et.",
            "Bu hata verdi, sonucu doğrula.",
        )
    ]
    candidates = []
    for index, event in enumerate(events):
        context = ()
        result = evaluate_harvest_event(event, manifest.limits)
        candidates.append(
            seal_harvest_candidate(
                event,
                partition="sessions",
                source_receipt=sha256_text(f"source-{index}"),
                context=context,
                tags=result.tags,
                score=result.score,
                selector_config_sha256=manifest.selector_config_sha256,
            )
        )

    first = HarvestReservoir(3, manifest.selector_config_sha256)
    second = HarvestReservoir(3, manifest.selector_config_sha256)
    for candidate in candidates:
        first.offer(candidate)
    for candidate in reversed(candidates):
        second.offer(candidate)

    assert len(first.candidates) <= 3
    assert [item.candidate_id for item in first.candidates] == [
        item.candidate_id for item in second.candidates
    ]


def test_reservoir_deduplicates_same_focus_across_sources_by_rank() -> None:
    manifest = _manifest(_limits(max_reservoir=4))
    event = normalized_event("user", "Bunu onaylıyorum, uygula ve test et.")
    lower = sealed_candidate(event, manifest, "a" * 64, 1)
    other_event = event.model_copy(
        update={"source_key": "b" * 64, "byte_start": 17, "record_sha256": "c" * 64}
    )
    higher = sealed_candidate(other_event, manifest, "d" * 64, 2)

    first = HarvestReservoir(4, manifest.selector_config_sha256)
    second = HarvestReservoir(4, manifest.selector_config_sha256)
    first.offer(lower)
    first.offer(higher)
    second.offer(higher)
    second.offer(lower)

    assert len(first.candidates) == len(second.candidates) == 1
    assert first.candidates[0].candidate_id == higher.candidate_id
    assert second.candidates[0].candidate_id == higher.candidate_id
    assert first.candidates[0].focus_sha256 == lower.focus_sha256 == higher.focus_sha256


def test_context_buffer_keeps_only_bounded_recent_user_assistant_messages() -> None:
    manifest = _manifest(_limits(max_context_messages=2, max_context_bytes=20))
    context = HarvestContextBuffer(manifest)
    context.observe(normalized_event("assistant", "old assistant context"))
    context.observe(normalized_event("user", "first decision"))
    context.observe(normalized_event("assistant", "second context"))

    assert len(context.messages) <= 2
    assert sum(len(item.content.encode()) for item in context.messages) <= 20
    assert all(item.speaker in {"user", "assistant"} for item in context.messages)
