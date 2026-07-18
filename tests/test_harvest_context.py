# ruff: noqa: RUF001 -- Turkish judgment fixtures mirror the selector vocabulary.

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from support.harvest import normalized_event

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.models.persona_harvest import HarvestLimits
from ynoy.persona_study.harvest_contract import seal_harvest_manifest
from ynoy.persona_study.harvest_events import HarvestContextBuffer, offer_harvest_event
from ynoy.persona_study.harvest_reservoir import HarvestReservoir
from ynoy.persona_study.harvest_signals import evaluate_harvest_event


def _manifest():
    now = datetime(2026, 2, 1, tzinfo=UTC)
    limits = HarvestLimits(max_context_bytes=2_000, max_artifact_bytes=20_000)
    return seal_harvest_manifest(
        run_id="1" * 64,
        source_study_id="2" * 64,
        freeze_sha256="3" * 64,
        boundary_ns=int((now + timedelta(days=1)).timestamp() * 1_000_000_000),
        stable_before_ns=int(now.timestamp() * 1_000_000_000),
        limits=limits,
        created_at=now,
        expires_at=now + timedelta(days=1),
        synthetic=True,
    )


@pytest.mark.parametrize(
    "text",
    [
        "<goal_context>Onaylıyorum, bunu uygula.</goal_context>",
        "<turn_aborted>Onaylıyorum, bunu uygula.</turn_aborted>",
        "# AGENTS.md instructions for F:/cerberus-repos\nOnaylıyorum, bunu uygula.",
    ],
)
def test_context_buffer_excludes_inert_runtime_content(text: str) -> None:
    context = HarvestContextBuffer(_manifest())

    context.observe(normalized_event("user", text))

    assert context.messages == ()


def test_context_buffer_retains_normal_dialogue() -> None:
    context = HarvestContextBuffer(_manifest())

    context.observe(normalized_event("user", "Bunu onaylıyorum."))
    context.observe(normalized_event("assistant", "Tamam, inceliyorum."))

    assert [item.speaker for item in context.messages] == ["user", "assistant"]


def test_review_findings_header_is_imported_content() -> None:
    result = evaluate_harvest_event(
        normalized_event("user", "# Review findings:\nOnaylıyorum, bunu uygula."),
        _manifest().limits,
    )

    assert result.exclusion == "quoted_or_imported_content"
    assert result.tags == ()


@pytest.mark.parametrize(
    "text",
    [
        "Automation: Onaylıyorum, bunu uygula ve test et.",
        "Automation ID: run-123; Onaylıyorum, bunu uygula ve test et.",
        "Tip: Try the Codex App. Onaylıyorum, bunu uygula ve test et.",
        "MCP startup incomplete; Onaylıyorum, bunu uygula ve test et.",
    ],
)
def test_automation_runtime_marker_is_imported_content(text: str) -> None:
    result = evaluate_harvest_event(normalized_event("user", text), _manifest().limits)

    assert result.exclusion == "quoted_or_imported_content"
    assert result.tags == ()


def test_context_buffer_excludes_remote_compact_error_but_keeps_adjacent_dialogue() -> None:
    context = HarvestContextBuffer(_manifest())
    context.observe(normalized_event("assistant", "Error running remote compact task: retrying"))
    context.observe(normalized_event("assistant", "Normal adjacent context remains."))

    assert [item.content for item in context.messages] == ["Normal adjacent context remains."]


def _item() -> DiscoveredCodexFile:
    return DiscoveredCodexFile(
        partition="sessions",
        path=Path("synthetic.jsonl"),
        relative=Path("2026/01/02/synthetic.jsonl"),
        file_bytes=100,
        modified_ns=1,
        device=0,
        inode=0,
    )


def test_api_error_runtime_marker_is_imported_content() -> None:
    result = evaluate_harvest_event(
        normalized_event("user", "● API Error: Onaylıyorum, bunu uygula ve test et."),
        _manifest().limits,
    )

    assert result.exclusion == "quoted_or_imported_content"
    assert result.tags == ()


def test_evidence_only_focus_without_context_is_rejected() -> None:
    manifest = _manifest()
    context = HarvestContextBuffer(manifest)
    exclusions: Counter[str] = Counter()
    reservoir = HarvestReservoir(3, manifest.selector_config_sha256)

    offer_harvest_event(
        reservoir,
        exclusions,
        normalized_event("user", "Lütfen kanıt ve test sonucu göster."),
        _item(),
        "a" * 64,
        context,
        manifest,
    )

    assert exclusions["low_signal_without_context"] == 1
    assert reservoir.candidates == ()


def test_evidence_only_focus_with_context_remains_eligible() -> None:
    manifest = _manifest()
    context = HarvestContextBuffer(manifest)
    context.observe(normalized_event("assistant", "İlgili teknik bağlam burada."))
    exclusions: Counter[str] = Counter()
    reservoir = HarvestReservoir(3, manifest.selector_config_sha256)

    offer_harvest_event(
        reservoir,
        exclusions,
        normalized_event("user", "Lütfen kanıt ve test sonucu göster."),
        _item(),
        "b" * 64,
        context,
        manifest,
    )

    assert exclusions == Counter()
    assert len(reservoir.candidates) == 1
