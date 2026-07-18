from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from ynoy.constants import DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES
from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.util import canonical_sha256, sha256_text


@dataclass(frozen=True, slots=True)
class LineageFile:
    item: DiscoveredCodexFile
    source_receipt: str
    thread_receipt: str
    parent_receipt: str | None
    session_start_ns: int
    component_receipt: str = ""


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, first: str, second: str) -> None:
        left, right = self.find(first), self.find(second)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def read_lineage(item: DiscoveredCodexFile) -> LineageFile:
    """Read only bounded session metadata needed for holdout lineage."""
    with open_stable_codex_file(item) as stream:
        first = stream.readline(DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES + 1)
    if len(first) > DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES:
        raise DataValidationError(
            "persona_holdout_metadata_oversized", "A holdout metadata record exceeds its limit."
        )
    try:
        record = json.loads(first)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "persona_holdout_metadata_invalid", "A holdout metadata record is invalid."
        ) from exc
    if not isinstance(record, Mapping) or record.get("type") != "session_meta":
        raise DataValidationError(
            "persona_holdout_session_meta_required", "Holdout sources require session metadata."
        )
    payload = record.get("payload")
    metadata = payload if isinstance(payload, Mapping) else {}
    thread = metadata.get("id") or metadata.get("session_id")
    if not isinstance(thread, str) or not thread:
        raise DataValidationError(
            "persona_holdout_thread_id_required", "Holdout lineage requires an opaque thread ID."
        )
    parent = _parent_thread(metadata)
    return LineageFile(
        item,
        file_receipt(item),
        sha256_text(f"holdout-thread:{thread}"),
        sha256_text(f"holdout-thread:{parent}") if parent is not None else None,
        session_start_ns(item),
    )


def component_lineages(values: tuple[LineageFile, ...]) -> tuple[LineageFile, ...]:
    """Resolve conservative components without opening missing parent content."""
    known_threads = {value.thread_receipt for value in values}
    _reject_conflicts_and_cycles(values, known_threads)
    graph = _UnionFind()
    for value in values:
        graph.find(value.thread_receipt)
        if value.parent_receipt:
            parent_node = value.parent_receipt
            if parent_node not in known_threads:
                parent_node = sha256_text(f"holdout-opaque-parent:{parent_node}")
            graph.union(value.thread_receipt, parent_node)
    groups: dict[str, list[str]] = defaultdict(list)
    for node in graph.parent:
        groups[graph.find(node)].append(node)
    receipts = {root: canonical_sha256(sorted(nodes)) for root, nodes in groups.items()}
    return tuple(
        LineageFile(
            item=value.item,
            source_receipt=value.source_receipt,
            thread_receipt=value.thread_receipt,
            parent_receipt=value.parent_receipt,
            session_start_ns=value.session_start_ns,
            component_receipt=receipts[graph.find(value.thread_receipt)],
        )
        for value in values
    )


def file_receipt(item: DiscoveredCodexFile) -> str:
    return canonical_sha256(
        (
            item.partition,
            item.relative.as_posix(),
            item.file_bytes,
            item.modified_ns,
            item.device,
            item.inode,
        )
    )


def session_start_ns(item: DiscoveredCodexFile) -> int:
    try:
        value = datetime.strptime(item.relative.name[8:27], "%Y-%m-%dT%H-%M-%S")
    except ValueError as exc:
        raise DataValidationError(
            "persona_holdout_filename_time_invalid",
            "A canonical rollout filename does not contain a valid session-start time.",
        ) from exc
    return int(value.replace(tzinfo=UTC).timestamp() * 1_000_000_000)


def _parent_thread(metadata: Mapping[object, object]) -> str | None:
    parent = metadata.get("parent_thread_id")
    if parent is None:
        return None
    if not isinstance(parent, str) or not parent.strip():
        raise DataValidationError(
            "persona_holdout_parent_thread_id_invalid",
            "Holdout lineage parent metadata must be a non-empty opaque ID or null.",
        )
    return parent


def _reject_conflicts_and_cycles(values: tuple[LineageFile, ...], known_threads: set[str]) -> None:
    parents: dict[str, str] = {}
    for value in values:
        parent = value.parent_receipt
        if parent is None or parent not in known_threads:
            continue
        previous = parents.setdefault(value.thread_receipt, parent)
        if previous != parent:
            raise DataValidationError(
                "persona_holdout_lineage_thread_conflict",
                "One thread has conflicting explicit lineage parents.",
            )
    state: dict[str, int] = {}
    for start in parents:
        _walk_parent_chain(start, parents, state)


def _walk_parent_chain(start: str, parents: dict[str, str], state: dict[str, int]) -> None:
    path: list[str] = []
    current = start
    while current in parents:
        if state.get(current) == 1:
            raise DataValidationError(
                "persona_holdout_lineage_cycle", "Holdout lineage contains a parent cycle."
            )
        if state.get(current) == 2:
            break
        state[current] = 1
        path.append(current)
        current = parents[current]
    for node in path:
        state[node] = 2
