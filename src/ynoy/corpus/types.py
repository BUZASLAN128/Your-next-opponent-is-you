from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from uuid import UUID
from zipfile import ZipFile, ZipInfo

from ynoy.constants import (
    DEFAULT_BRANCH_MAX_DEPTH,
    DEFAULT_BRANCH_MAX_MEMBERSHIP_PAIRS,
    DEFAULT_CONVERSATION_MAX_NODES,
)
from ynoy.errors import DataValidationError
from ynoy.models import (
    ClaimHolder,
    InventoryManifest,
    SourceAuthority,
    SourceEvent,
    Speaker,
)


class SourceAdapter(Protocol):
    name: str

    def inventory(self, path: Path, *, synthetic: bool) -> InventoryManifest: ...

    def iter_events(
        self, path: Path, *, manifest: InventoryManifest, import_run_id: UUID
    ) -> Iterator[SourceEvent]: ...


@dataclass(slots=True)
class NormalizationStats:
    normalized: int = 0
    excluded: int = 0
    speaker_counts: Counter[str] = field(default_factory=Counter)
    warnings: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class InventoryCounts:
    conversations: int
    messages: int
    branches: int
    malformed: int
    excluded_parts: int
    speakers: Counter[str]


def as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def as_sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def speaker_from_message(message: Mapping[str, Any]) -> Speaker:
    author = as_mapping(message.get("author"))
    role = str(author.get("role", "unknown")).casefold()
    return {
        "user": Speaker.USER,
        "assistant": Speaker.ASSISTANT,
        "system": Speaker.SYSTEM,
        "tool": Speaker.TOOL,
    }.get(role, Speaker.UNKNOWN)


def authority_for_speaker(speaker: Speaker) -> SourceAuthority:
    return {
        Speaker.USER: SourceAuthority.USER_TURN_UNATTRIBUTED,
        Speaker.ASSISTANT: SourceAuthority.ASSISTANT_CONTEXT,
        Speaker.SYSTEM: SourceAuthority.SYSTEM_CONTROL,
        Speaker.TOOL: SourceAuthority.THIRD_PARTY_CONTEXT,
        Speaker.THIRD_PARTY: SourceAuthority.THIRD_PARTY_CONTEXT,
        Speaker.UNKNOWN: SourceAuthority.UNKNOWN,
    }[speaker]


def claim_holder_for_speaker(speaker: Speaker) -> ClaimHolder:
    return {
        Speaker.USER: ClaimHolder.UNKNOWN,
        Speaker.ASSISTANT: ClaimHolder.ASSISTANT,
        Speaker.SYSTEM: ClaimHolder.UNKNOWN,
        Speaker.TOOL: ClaimHolder.THIRD_PARTY,
        Speaker.THIRD_PARTY: ClaimHolder.THIRD_PARTY,
        Speaker.UNKNOWN: ClaimHolder.UNKNOWN,
    }[speaker]


def source_event_metadata(
    message: Mapping[str, object], branch_count: int, speaker: Speaker
) -> dict[str, object]:
    return {
        "content_type": str(as_mapping(message.get("content")).get("content_type", "unknown")),
        "branch_membership_count": branch_count,
        "imported_instruction_is_inert": True,
        "claim_attribution_status": (
            "unreviewed_span" if speaker == Speaker.USER else "speaker_context_only"
        ),
    }


def event_time(message: Mapping[str, Any]) -> datetime | None:
    raw = message.get("create_time")
    if isinstance(raw, int | float):
        try:
            return datetime.fromtimestamp(float(raw), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def text_content(message: Mapping[str, Any]) -> tuple[str, int]:
    content = as_mapping(message.get("content"))
    accepted: list[str] = []
    excluded = 0
    for part in as_sequence(content.get("parts")):
        if isinstance(part, str):
            accepted.append(part)
        else:
            excluded += 1
    return "\n".join(accepted).strip(), excluded


def conversation_files(archive: ZipFile) -> list[ZipInfo]:
    selected = []
    for info in archive.infolist():
        name = PurePosixPath(info.filename).name.casefold()
        if name == "conversations.json" or (
            name.startswith("conversations-") and name.endswith(".json")
        ):
            selected.append(info)
    return sorted(selected, key=lambda info: info.filename.casefold())


def branch_membership(
    mapping: Mapping[str, Any],
    *,
    max_nodes: int = DEFAULT_CONVERSATION_MAX_NODES,
    max_depth: int = DEFAULT_BRANCH_MAX_DEPTH,
    max_pairs: int = DEFAULT_BRANCH_MAX_MEMBERSHIP_PAIRS,
) -> dict[str, tuple[str, ...]]:
    if len(mapping) > max_nodes:
        raise DataValidationError(
            "conversation_node_limit",
            "A conversation exceeds the configured node limit.",
            details={"limit": max_nodes},
        )
    leaves = [
        str(node_id)
        for node_id, raw_node in mapping.items()
        if not as_sequence(as_mapping(raw_node).get("children"))
    ]
    memberships: dict[str, set[str]] = defaultdict(set)
    pair_count = 0
    for leaf in leaves:
        pair_count += _walk_branch(
            mapping,
            leaf,
            memberships,
            max_depth=max_depth,
            remaining_pairs=max_pairs - pair_count,
        )
    return {key: tuple(sorted(value)) for key, value in memberships.items()}


def _walk_branch(
    mapping: Mapping[str, Any],
    leaf: str,
    memberships: dict[str, set[str]],
    *,
    max_depth: int,
    remaining_pairs: int,
) -> int:
    current: str | None = leaf
    visited: set[str] = set()
    pair_count = 0
    while current and current not in visited:
        if len(visited) >= max_depth:
            raise DataValidationError(
                "conversation_branch_depth_limit",
                "A conversation branch exceeds the configured depth limit.",
                details={"limit": max_depth},
            )
        if pair_count >= remaining_pairs:
            raise DataValidationError(
                "conversation_branch_membership_limit",
                "Conversation branch expansion exceeds the configured work limit.",
                details={"limit": remaining_pairs},
            )
        visited.add(current)
        memberships[current].add(leaf)
        pair_count += 1
        parent = as_mapping(mapping.get(current)).get("parent")
        current = str(parent) if parent is not None else None
    return pair_count
