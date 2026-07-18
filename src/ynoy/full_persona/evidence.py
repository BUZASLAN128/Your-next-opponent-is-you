# ruff: noqa: RUF001 -- Turkish signal vocabulary is intentional.

from __future__ import annotations

import re
from collections import deque
from datetime import UTC, datetime
from typing import Any, Literal, cast

from ynoy.models import (
    ClaimHolder,
    CodexActorOrigin,
    NormalizedCodexEvent,
    SourceAuthority,
    Speaker,
)
from ynoy.models.full_persona import (
    EvidenceRole,
    FullCorpusContext,
    FullCorpusEvidence,
    FullCorpusLimits,
    FullCorpusSource,
)
from ynoy.util import canonical_sha256, sha256_text

_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("correction", re.compile(r"\b(yanlış|düzelt|kaldır|sil|öyle değil|fixle)\b", re.I)),
    (
        "decision",
        re.compile(r"\b(onaylıyorum|kalsın|devam et|yapalım|istiyorum|olmalı|uygula)\b", re.I),
    ),
    (
        "evidence_demand",
        re.compile(r"\b(kanıt|test|doğrula|incele|araştır|kaynak|review|benchmark)\b", re.I),
    ),
    ("scope_change", re.compile(r"\b(sadece|yalnız|hiçbir|şimdilik|sonra|önce|sınır)\b", re.I)),
    ("uncertainty", re.compile(r"\b(bilmiyorum|emin değilim|sana bırakıyorum|kararsız)\b", re.I)),
    (
        "outcome_feedback",
        re.compile(r"\b(başarılı|çalıştı|çalışmıyor|hata|çöktü|iyi oldu|kötü oldu)\b", re.I),
    ),
)
_CONTROL_PREFIXES = (
    "<codex_internal_context",
    "<environment_context>",
    "<goal_context>",
    "<recommended_plugins>",
    "# agents.md instructions for",
)


class EvidenceContext:
    def __init__(self, limits: FullCorpusLimits, values: tuple[FullCorpusContext, ...] = ()):
        self.limits = limits
        self._values: deque[FullCorpusContext] = deque(values)
        self._trim()

    @property
    def values(self) -> tuple[FullCorpusContext, ...]:
        return tuple(self._values)

    def observe(self, event: NormalizedCodexEvent) -> None:
        if event.status != "dialogue" or event.content is None:
            return
        if event.structural_role not in {Speaker.USER, Speaker.ASSISTANT}:
            return
        content = event.content.strip()
        if not content or _is_control(content):
            return
        if len(content.encode("utf-8")) > self.limits.max_context_bytes:
            return
        speaker: Literal["user", "assistant"] = (
            "user" if event.structural_role == Speaker.USER else "assistant"
        )
        self._values.append(
            FullCorpusContext(speaker=speaker, content=content, content_sha256=sha256_text(content))
        )
        self._trim()

    def _trim(self) -> None:
        while len(self._values) > self.limits.max_context_messages or self._bytes() > (
            self.limits.max_context_bytes
        ):
            self._values.popleft()

    def _bytes(self) -> int:
        return sum(len(item.content.encode("utf-8")) for item in self._values)


def evidence_from_event(
    event: NormalizedCodexEvent,
    source: FullCorpusSource,
    context: tuple[FullCorpusContext, ...],
    limits: FullCorpusLimits,
) -> tuple[FullCorpusEvidence | None, str | None]:
    exclusion = _event_exclusion(event, limits)
    if exclusion is not None:
        return None, exclusion
    assert event.content is not None
    assert event.content_sha256 is not None
    assert event.conversation_key is not None
    content = event.content.strip()
    role = _role(content)
    if role is None:
        return None, "control_or_imported_content"
    event_time, time_basis = _evidence_time(event, source)
    payload = {
        "evidence_id": sha256_text(
            f"{source.source_receipt}:{event.byte_start}:{event.record_sha256}"
        ),
        "source_key": source.source_key,
        "source_receipt": source.source_receipt,
        "blob_sha256": source.blob_sha256,
        "byte_start": event.byte_start,
        "byte_length": event.byte_length,
        "line_number": event.line_number,
        "record_sha256": event.record_sha256,
        "conversation_key": event.conversation_key,
        "turn_key": event.turn_key,
        "event_time": event_time,
        "time_basis": time_basis,
        "role": role,
        "signal_tags": tuple(name for name, pattern in _SIGNALS if pattern.search(content)),
        "context": context,
        "content": content,
        "content_sha256": sha256_text(content),
    }
    draft = cast(Any, FullCorpusEvidence).model_construct(**payload, evidence_sha256="0" * 64)
    return (
        FullCorpusEvidence.model_validate(
            {
                **payload,
                "evidence_sha256": canonical_sha256(
                    draft.model_dump(mode="json", exclude={"evidence_sha256"})
                ),
            }
        ),
        None,
    )


def _event_exclusion(event: NormalizedCodexEvent, limits: FullCorpusLimits) -> str | None:
    if event.status != "dialogue":
        return event.exclusion_reason or "non_dialogue"
    if (
        event.actor_origin != CodexActorOrigin.USER_CANDIDATE
        or event.structural_role != Speaker.USER
        or event.claim_holder != ClaimHolder.UNKNOWN
        or event.source_authority != SourceAuthority.USER_TURN_UNATTRIBUTED
    ):
        return "non_user_origin"
    if event.content is None or not event.content.strip():
        return "empty_user_content"
    if event.conversation_key is None:
        return "conversation_unknown"
    if len(event.content.encode("utf-8")) > limits.max_evidence_bytes:
        return "evidence_oversized"
    return None


def _evidence_time(
    event: NormalizedCodexEvent, source: FullCorpusSource
) -> tuple[datetime, Literal["event", "session_start"]]:
    if event.event_time is not None:
        return event.event_time, "event"
    return datetime.fromtimestamp(source.session_start_ns / 1e9, tz=UTC), "session_start"


def _role(content: str) -> EvidenceRole | None:
    lowered = content.lstrip().casefold()
    if any(lowered.startswith(value) for value in _CONTROL_PREFIXES):
        return None
    if "# files mentioned by the user:" in lowered and "# my request" not in lowered:
        return None
    if lowered.startswith("please implement this plan"):
        return EvidenceRole.PROJECT
    if "# files mentioned by the user:" in lowered or "```" in content or "\n> " in content:
        return EvidenceRole.MIXED
    if re.search(r"\b(implement|fixle|push|commit|repo|kod|test|dosya|branch|pr)\b", content, re.I):
        return EvidenceRole.PROJECT
    return EvidenceRole.DIRECT


def _is_control(content: str) -> bool:
    lowered = content.lstrip().casefold()
    return any(lowered.startswith(value) for value in _CONTROL_PREFIXES)
