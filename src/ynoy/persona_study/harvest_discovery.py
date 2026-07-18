from __future__ import annotations

import os
import re
import stat
from bisect import insort
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ynoy.corpus.codex_discovery import DiscoveredCodexFile, Partition, resolve_codex_root
from ynoy.errors import DataValidationError
from ynoy.models.persona_harvest import HarvestFileCursor, HarvestLimits
from ynoy.persona_study.lineage import session_start_ns
from ynoy.util import sha256_text

_YEAR = re.compile(r"^20\d{2}$")
_MONTH = re.compile(r"^(0[1-9]|1[0-2])$")
_DAY = re.compile(r"^(0[1-9]|[12]\d|3[01])$")
_ROLLOUT = re.compile(
    r"^rollout-20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
    r"T([01]\d|2[0-3])-[0-5]\d-[0-5]\d-[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$"
)


@dataclass(frozen=True, slots=True)
class HarvestDiscoveryBatch:
    root: Path
    files: tuple[DiscoveredCodexFile, ...]
    anchor: DiscoveredCodexFile | None
    has_more: bool
    entries_scanned: int


@dataclass(slots=True)
class _ScanBudget:
    maximum: int
    visited: int = 0

    def observe(self) -> None:
        self.visited += 1
        if self.visited > self.maximum:
            raise DataValidationError(
                "codex_harvest_entry_limit",
                "The bounded Codex harvest exceeded its metadata entry limit.",
            )


def discover_harvest_batch(
    root: Path,
    limits: HarvestLimits,
    *,
    stable_before_ns: int,
    holdout_boundary_ns: int,
    previous: HarvestFileCursor | None,
) -> HarvestDiscoveryBatch:
    """Select the next canonical files with O(max_files) retained metadata."""
    source = resolve_codex_root(root)
    budget = _ScanBudget(limits.max_entries)
    selected: list[tuple[str, DiscoveredCodexFile]] = []
    eligible_after = 0
    anchor: DiscoveredCodexFile | None = None
    start_key = None if previous is None else previous.sort_key
    include_start = previous is not None and not previous.complete
    for item in _iter_canonical_files(source, budget):
        if previous is not None and _locator(item) == (
            previous.partition,
            previous.relative_locator,
        ):
            anchor = item
        if not _eligible(item, stable_before_ns, holdout_boundary_ns, limits):
            continue
        key = harvest_file_sort_key(item)
        if start_key is not None and (key < start_key or (key == start_key and not include_start)):
            continue
        eligible_after += 1
        insort(selected, (key, item))
        if len(selected) > limits.max_files:
            selected.pop()
    return HarvestDiscoveryBatch(
        source,
        tuple(item for _, item in selected),
        anchor,
        eligible_after > len(selected),
        budget.visited,
    )


def harvest_file_sort_key(item: DiscoveredCodexFile) -> str:
    locator = f"{item.partition}:{item.relative.as_posix()}"
    return f"{sha256_text(locator)}:{locator}"


def _eligible(
    item: DiscoveredCodexFile,
    stable_before_ns: int,
    holdout_boundary_ns: int,
    limits: HarvestLimits,
) -> bool:
    return bool(
        0 < item.file_bytes <= limits.max_file_bytes
        and item.modified_ns <= stable_before_ns
        and session_start_ns(item) < holdout_boundary_ns
    )


def _iter_canonical_files(root: Path, budget: _ScanBudget) -> Iterator[DiscoveredCodexFile]:
    found = False
    sessions = root / "sessions"
    archived = root / "archived_sessions"
    if sessions.exists():
        found = True
        _require_real_directory(sessions)
        yield from _walk_sessions(sessions, budget)
    if archived.exists():
        found = True
        _require_real_directory(archived)
        yield from _walk_archived(archived, budget)
    if not found:
        raise DataValidationError(
            "codex_partitions_missing", "No canonical Codex session partition was found."
        )


def _walk_sessions(root: Path, budget: _ScanBudget) -> Iterator[DiscoveredCodexFile]:
    for year in _entries(root, budget):
        if not _directory_named(year, _YEAR):
            _reject_unexpected_directory(year)
            continue
        for month in _entries(Path(year.path), budget):
            if not _directory_named(month, _MONTH):
                _reject_unexpected_directory(month)
                continue
            for day in _entries(Path(month.path), budget):
                if not _directory_named(day, _DAY):
                    _reject_unexpected_directory(day)
                    continue
                for entry in _entries(Path(day.path), budget):
                    if entry.is_dir(follow_symlinks=False):
                        _reject_unexpected_directory(entry)
                    elif _ROLLOUT.fullmatch(entry.name):
                        yield _file_metadata(entry, root, "sessions")


def _walk_archived(root: Path, budget: _ScanBudget) -> Iterator[DiscoveredCodexFile]:
    for entry in _entries(root, budget):
        if entry.is_dir(follow_symlinks=False):
            _reject_unexpected_directory(entry)
        elif _ROLLOUT.fullmatch(entry.name):
            yield _file_metadata(entry, root, "archived_sessions")


def _entries(path: Path, budget: _ScanBudget) -> Iterator[os.DirEntry[str]]:
    try:
        with os.scandir(path) as stream:
            for entry in stream:
                budget.observe()
                if entry.is_symlink() or Path(entry.path).is_junction():
                    raise DataValidationError(
                        "codex_symlink_rejected", "Codex harvest does not follow links."
                    )
                yield entry
    except OSError as exc:
        raise DataValidationError(
            "codex_partition_unreadable", "A canonical Codex partition is unreadable."
        ) from exc


def _directory_named(entry: os.DirEntry[str], pattern: re.Pattern[str]) -> bool:
    return entry.is_dir(follow_symlinks=False) and bool(pattern.fullmatch(entry.name))


def _reject_unexpected_directory(entry: os.DirEntry[str]) -> None:
    if entry.is_dir(follow_symlinks=False):
        raise DataValidationError(
            "codex_noncanonical_directory",
            "Codex harvest rejected a noncanonical directory without scanning it.",
        )


def _file_metadata(
    entry: os.DirEntry[str], root: Path, partition: Partition
) -> DiscoveredCodexFile:
    try:
        # On Windows, DirEntry.stat() may report a zero device/inode pair while
        # os.stat() and fstat() expose the stable file identity used by the reader.
        metadata = os.stat(entry.path, follow_symlinks=False)
    except OSError as exc:
        raise DataValidationError(
            "codex_session_unreadable", "A canonical Codex session file is unreadable."
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DataValidationError(
            "codex_special_file_rejected", "Codex harvest accepts regular files only."
        )
    path = Path(entry.path)
    return DiscoveredCodexFile(
        partition,
        path,
        path.relative_to(root),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_dev,
        metadata.st_ino,
    )


def _require_real_directory(path: Path) -> None:
    if path.is_symlink() or path.is_junction() or not path.is_dir():
        raise DataValidationError(
            "codex_partition_invalid", "Canonical Codex partitions must be real directories."
        )


def _locator(item: DiscoveredCodexFile) -> tuple[str, str]:
    return item.partition, item.relative.as_posix()
