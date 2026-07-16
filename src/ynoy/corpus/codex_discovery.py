from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Literal

from ynoy.constants import (
    DEFAULT_CODEX_INVENTORY_MAX_DEPTH,
    DEFAULT_CODEX_INVENTORY_MAX_ENTRIES,
    DEFAULT_CODEX_INVENTORY_MAX_FILES,
    DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES,
)
from ynoy.errors import DataValidationError

Partition = Literal["sessions", "archived_sessions"]
PARTITIONS: tuple[Partition, ...] = ("sessions", "archived_sessions")
_YEAR = re.compile(r"^20\d{2}$")
_MONTH = re.compile(r"^(0[1-9]|1[0-2])$")
_DAY = re.compile(r"^(0[1-9]|[12]\d|3[01])$")
_ROLLOUT = re.compile(
    r"^rollout-20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
    r"T([01]\d|2[0-3])-[0-5]\d-[0-5]\d-[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$"
)


@dataclass(frozen=True, slots=True)
class CodexInventoryLimits:
    max_files: int = DEFAULT_CODEX_INVENTORY_MAX_FILES
    max_entries: int = DEFAULT_CODEX_INVENTORY_MAX_ENTRIES
    max_depth: int = DEFAULT_CODEX_INVENTORY_MAX_DEPTH
    max_first_record_bytes: int = DEFAULT_CODEX_INVENTORY_MAX_FIRST_RECORD_BYTES

    def __post_init__(self) -> None:
        positive = (self.max_files, self.max_entries, self.max_first_record_bytes)
        if any(value < 1 for value in positive) or self.max_depth < 0:
            raise DataValidationError(
                "codex_inventory_invalid_limit",
                "Codex inventory limits must be positive; directory depth may be zero.",
            )


@dataclass(frozen=True, slots=True)
class DiscoveredCodexFile:
    partition: Partition
    path: Path
    relative: Path
    file_bytes: int
    modified_ns: int
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class CodexDiscovery:
    files: tuple[DiscoveredCodexFile, ...]
    ignored_noncanonical_files: int


@dataclass(frozen=True, slots=True)
class _PartitionDiscovery:
    files: tuple[DiscoveredCodexFile, ...]
    ignored_files: int
    visited_entries: int


def resolve_codex_root(root: Path) -> Path:
    try:
        source = root.expanduser().resolve(strict=True)
    except OSError as exc:
        raise DataValidationError(
            "codex_root_unavailable", "The explicitly selected Codex root is unavailable."
        ) from exc
    if not source.is_dir():
        raise DataValidationError("codex_root_not_directory", "Codex root must be a directory.")
    return source


def discover_codex_sessions(root: Path, limits: CodexInventoryLimits) -> CodexDiscovery:
    files: list[DiscoveredCodexFile] = []
    ignored = visited = 0
    found_partition = False
    for partition in PARTITIONS:
        partition_root = root / partition
        if not partition_root.exists():
            continue
        found_partition = True
        _validate_partition(partition_root)
        result = _walk_partition(
            partition_root,
            partition,
            limits,
            entry_budget=limits.max_entries - visited,
            file_budget=limits.max_files - len(files),
        )
        files.extend(result.files)
        ignored += result.ignored_files
        visited += result.visited_entries
    if not found_partition:
        raise DataValidationError(
            "codex_partitions_missing", "No canonical Codex session partition was found."
        )
    files.sort(key=lambda item: (item.partition, item.relative.as_posix()))
    return CodexDiscovery(tuple(files), ignored)


def discovery_key(discovery: CodexDiscovery) -> tuple[object, ...]:
    locators = tuple(
        (
            item.partition,
            item.relative.as_posix(),
            item.file_bytes,
            item.modified_ns,
            item.device,
            item.inode,
        )
        for item in discovery.files
    )
    return locators, discovery.ignored_noncanonical_files


def _validate_partition(path: Path) -> None:
    if path.is_symlink() or path.is_junction() or not path.is_dir():
        raise DataValidationError(
            "codex_partition_invalid", "Canonical Codex partitions must be real directories."
        )


def _walk_partition(
    root: Path,
    partition: Partition,
    limits: CodexInventoryLimits,
    *,
    entry_budget: int,
    file_budget: int,
) -> _PartitionDiscovery:
    selected: list[DiscoveredCodexFile] = []
    ignored = visited = 0
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        children = _children(current, entry_budget - visited, limits.max_entries)
        visited += len(children)
        for child in children:
            ignored += _handle_child(
                child,
                root,
                partition,
                depth,
                limits,
                file_budget,
                selected,
                stack,
            )
    return _PartitionDiscovery(tuple(selected), ignored, visited)


def _children(path: Path, budget: int, configured_limit: int) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(path) as stream:
            children = list(islice(stream, max(budget, 0) + 1))
    except OSError as exc:
        raise DataValidationError(
            "codex_partition_unreadable", "A canonical Codex partition is unreadable."
        ) from exc
    if len(children) > budget:
        raise DataValidationError(
            "codex_inventory_entry_limit",
            "Codex metadata inventory exceeds the configured entry limit.",
            details={"limit": configured_limit},
        )
    return sorted(children, key=lambda item: item.name.casefold())


def _handle_child(
    child: os.DirEntry[str],
    root: Path,
    partition: Partition,
    depth: int,
    limits: CodexInventoryLimits,
    file_budget: int,
    selected: list[DiscoveredCodexFile],
    stack: list[tuple[Path, int]],
) -> int:
    path = Path(child.path)
    if child.is_symlink() or path.is_junction():
        raise DataValidationError(
            "codex_symlink_rejected", "Codex metadata inventory does not follow links."
        )
    relative = path.relative_to(root)
    if child.is_dir(follow_symlinks=False):
        _accept_directory(partition, relative, depth, limits, path, stack)
        return 0
    if child.is_file(follow_symlinks=False) and _is_canonical_file(partition, relative):
        if len(selected) >= file_budget:
            raise DataValidationError(
                "codex_inventory_file_limit",
                "Codex metadata inventory exceeds the configured file limit.",
                details={"limit": limits.max_files},
            )
        selected.append(_file_metadata(path, root, partition))
        return 0
    if child.is_file(follow_symlinks=False):
        return 1
    raise DataValidationError(
        "codex_special_file_rejected",
        "Codex metadata inventory accepts regular files and directories only.",
    )


def _accept_directory(
    partition: Partition,
    relative: Path,
    depth: int,
    limits: CodexInventoryLimits,
    path: Path,
    stack: list[tuple[Path, int]],
) -> None:
    if partition != "sessions" or not _is_date_prefix(relative.parts):
        raise DataValidationError(
            "codex_noncanonical_directory",
            "Codex metadata inventory rejected a noncanonical directory without scanning it.",
        )
    if depth >= limits.max_depth:
        raise DataValidationError(
            "codex_inventory_depth_limit",
            "Codex metadata inventory exceeds the configured directory depth.",
            details={"limit": limits.max_depth},
        )
    stack.append((path, depth + 1))


def _is_date_prefix(parts: tuple[str, ...]) -> bool:
    validators = (_YEAR, _MONTH, _DAY)
    return 1 <= len(parts) <= 3 and all(
        validators[index].fullmatch(value) for index, value in enumerate(parts)
    )


def _is_canonical_file(partition: Partition, relative: Path) -> bool:
    parts = relative.parts
    location_ok = len(parts) == 1 if partition == "archived_sessions" else len(parts) == 4
    return bool(location_ok and _ROLLOUT.fullmatch(relative.name))


def _file_metadata(path: Path, root: Path, partition: Partition) -> DiscoveredCodexFile:
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise DataValidationError(
            "codex_session_unreadable", "A canonical Codex session file is unreadable."
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DataValidationError(
            "codex_link_swap_rejected",
            "Codex session identity changed during discovery.",
        )
    return DiscoveredCodexFile(
        partition,
        path,
        path.relative_to(root),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_dev,
        metadata.st_ino,
    )
