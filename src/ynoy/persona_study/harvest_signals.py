# ruff: noqa: RUF001 -- Turkish signal vocabulary is intentional.

from __future__ import annotations

import re
from dataclasses import dataclass

from ynoy.models import (
    ClaimHolder,
    CodexActorOrigin,
    NormalizedCodexEvent,
    SourceAuthority,
    Speaker,
)
from ynoy.models.persona_harvest import HarvestLimits, HarvestSignal

_SIGNALS: tuple[tuple[HarvestSignal, int, re.Pattern[str]], ...] = (
    (
        "correction",
        6,
        re.compile(r"\b(yanlış|düzelt|kaldır|çıkar|sil|öyle değil|demek istediğim|fixle)\b", re.I),
    ),
    (
        "decision",
        5,
        re.compile(
            r"\b(onaylıyorum|kalsın|devam et|yapalım|yap bakalım|istiyorum|istemiyorum|"
            r"olmalı|olmasın|karar|seçelim|uygula|implement|approve|reject|keep it)\b",
            re.I,
        ),
    ),
    (
        "evidence_demand",
        5,
        re.compile(
            r"\b(kanıt|test(?:ler|leri| sonucu| et| ettin| geçiş)|doğrula|incele|araştır|"
            r"kaynak|review|verify|evidence|benchmark)\b",
            re.I,
        ),
    ),
    (
        "scope_change",
        4,
        re.compile(
            r"\b(sadece|yalnız|hiçbir|şimdilik|sonra|önce|kapsam|sınır|hariç|"
            r"only|never|scope|limit|before|after)\b",
            re.I,
        ),
    ),
    (
        "abstention",
        3,
        re.compile(
            r"\b(bilmiyorum|emin değilim|sana bırakıyorum|sen karar ver|kararsız|"
            r"not sure|you decide|defer)\b",
            re.I,
        ),
    ),
    (
        "outcome_feedback",
        3,
        re.compile(
            r"\b(başarılı|çalıştı|çalışmıyor|hata|çöktü|iyi oldu|kötü oldu|"
            r"passed|failed|works|broken|crash|regression)\b",
            re.I,
        ),
    ),
)
_INERT_MARKERS = (
    "<codex_internal_context",
    "<environment_context>",
    "<goal_context>",
    "<turn_aborted>",
    "# agents.md instructions for",
    "# context from my ide setup:",
    "# review findings:",
    "● api error:",
    "automation:",
    "automation id:",
    "error running remote compact task:",
    "mcp startup incomplete",
    "tip: try the codex app.",
    "<recommended_plugins>",
    "# files mentioned by the user:",
    "```",
    "\n> ",
)


@dataclass(frozen=True, slots=True)
class HarvestSignalResult:
    tags: tuple[HarvestSignal, ...] = ()
    score: int = 0
    exclusion: str | None = None


def evaluate_harvest_event(
    event: NormalizedCodexEvent, limits: HarvestLimits
) -> HarvestSignalResult:
    """Classify one normalized event without claiming represented-user authorship."""
    exclusion = _structural_exclusion(event)
    if exclusion is not None:
        return HarvestSignalResult(exclusion=exclusion)
    assert event.content is not None
    content_bytes = len(event.content.encode("utf-8"))
    if content_bytes > limits.max_focus_bytes:
        return HarvestSignalResult(exclusion="focus_oversized")
    if is_inert_or_imported_content(event.content):
        return HarvestSignalResult(exclusion="quoted_or_imported_content")
    tags = tuple(tag for tag, _, pattern in _SIGNALS if pattern.search(event.content))
    if not tags:
        return HarvestSignalResult(exclusion="no_judgment_signal")
    if tags == ("evidence_demand",) and len(re.findall(r"\w+", event.content)) < 5:
        return HarvestSignalResult(exclusion="low_signal_short_focus")
    weights = {tag: weight for tag, weight, _ in _SIGNALS}
    score = sum(weights[tag] for tag in tags) + min(len(tags) - 1, 3)
    return HarvestSignalResult(tags, score)


def is_inert_or_imported_content(content: str) -> bool:
    lowered = content.casefold()
    return lowered.startswith("> ") or any(marker in lowered for marker in _INERT_MARKERS)


def _structural_exclusion(event: NormalizedCodexEvent) -> str | None:
    if event.status != "dialogue":
        return event.exclusion_reason or "non_dialogue"
    if event.actor_origin != CodexActorOrigin.USER_CANDIDATE:
        return "non_user_origin"
    if event.structural_role != Speaker.USER:
        return "non_user_speaker"
    if event.claim_holder != ClaimHolder.UNKNOWN:
        return "claim_holder_not_unknown"
    if event.source_authority != SourceAuthority.USER_TURN_UNATTRIBUTED:
        return "user_authority_not_unattributed"
    if event.duplicate_of is not None:
        return "duplicate_representation"
    if event.content is None or not event.content.strip():
        return "empty_dialogue"
    if event.event_time is None:
        return "event_time_unknown"
    if event.conversation_key is None:
        return "conversation_unknown"
    return None
