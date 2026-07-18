from __future__ import annotations

from collections import Counter, deque
from typing import Literal

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.models import NormalizedCodexEvent, Speaker
from ynoy.models.persona_harvest import HarvestContextMessage, HarvestManifest
from ynoy.persona_study.harvest_contract import seal_harvest_candidate
from ynoy.persona_study.harvest_reservoir import HarvestReservoir
from ynoy.persona_study.harvest_signals import evaluate_harvest_event
from ynoy.util import sha256_text


class HarvestContextBuffer:
    def __init__(self, manifest: HarvestManifest) -> None:
        self.manifest = manifest
        self._items: deque[HarvestContextMessage] = deque()

    @property
    def messages(self) -> tuple[HarvestContextMessage, ...]:
        return tuple(self._items)

    def observe(self, event: NormalizedCodexEvent) -> None:
        if event.status != "dialogue" or event.content is None:
            return
        if event.structural_role not in {Speaker.USER, Speaker.ASSISTANT}:
            return
        if len(event.content.encode("utf-8")) > self.manifest.limits.max_context_bytes:
            return
        speaker: Literal["user", "assistant"] = (
            "user" if event.structural_role == Speaker.USER else "assistant"
        )
        self._items.append(
            HarvestContextMessage(
                speaker=speaker,
                content=event.content,
                content_sha256=sha256_text(event.content),
            )
        )
        self._trim()

    def _trim(self) -> None:
        limits = self.manifest.limits
        while len(self._items) > limits.max_context_messages or self._byte_count() > (
            limits.max_context_bytes
        ):
            self._items.popleft()

    def _byte_count(self) -> int:
        return sum(len(item.content.encode("utf-8")) for item in self._items)


def offer_harvest_event(
    reservoir: HarvestReservoir,
    exclusions: Counter[str],
    event: NormalizedCodexEvent,
    item: DiscoveredCodexFile,
    source_receipt: str,
    context: HarvestContextBuffer,
    manifest: HarvestManifest,
) -> None:
    result = evaluate_harvest_event(event, manifest.limits)
    if result.exclusion is not None:
        exclusions[_bounded_exclusion(result.exclusion)] += 1
        return
    candidate = seal_harvest_candidate(
        event,
        partition=item.partition,
        source_receipt=source_receipt,
        context=context.messages,
        tags=result.tags,
        score=result.score,
        selector_config_sha256=manifest.selector_config_sha256,
    )
    reservoir.offer(candidate)


def _bounded_exclusion(value: str) -> str:
    allowed = {
        "duplicate_representation",
        "empty_dialogue",
        "event_time_unknown",
        "focus_oversized",
        "no_judgment_signal",
        "non_dialogue",
        "non_user_origin",
        "quoted_or_imported_content",
        "subagent_or_delegation",
    }
    return value if value in allowed else "other"
