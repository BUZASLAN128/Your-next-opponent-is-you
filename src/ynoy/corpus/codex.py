from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import UUID

from ynoy.constants import CODEX_METADATA_PARSER_VERSION
from ynoy.corpus.codex_discovery import (
    CodexInventoryLimits,
    DiscoveredCodexFile,
    discover_codex_sessions,
    discovery_key,
    resolve_codex_root,
)
from ynoy.corpus.codex_reader import inspect_first_record
from ynoy.errors import DataValidationError
from ynoy.models import (
    CodexInventoryEntry,
    CodexMetadataInventory,
    CodexMonthSummary,
    DataClass,
)
from ynoy.util import canonical_sha256, new_id, sha256_text, utc_now

SYNTHETIC_MARKER = b"YNOY_SYNTHETIC_CODEX_FIXTURE_V1\n"


class CodexMetadataAdapter:
    """Inventory canonical local Codex session files without copying content fields."""

    name = "codex_local_sessions_metadata"

    def __init__(self, limits: CodexInventoryLimits | None = None):
        self.limits = limits or CodexInventoryLimits()

    def inventory(
        self,
        root: Path,
        *,
        synthetic: bool,
        record_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> CodexMetadataInventory:
        source = resolve_codex_root(root)
        if synthetic:
            assert_synthetic_codex_root(source)
        before = discover_codex_sessions(source, self.limits)
        entries = tuple(_entry(item, self.limits) for item in before.files)
        after = discover_codex_sessions(source, self.limits)
        if discovery_key(before) != discovery_key(after):
            raise DataValidationError(
                "codex_source_changed_during_inventory",
                "Canonical Codex session files changed during metadata inventory.",
            )
        return _build_manifest(
            entries,
            ignored_noncanonical=before.ignored_noncanonical_files,
            synthetic=synthetic,
            record_id=record_id,
            created_at=created_at,
        )


def assert_synthetic_codex_root(root: Path) -> None:
    path = root / ".ynoy-synthetic-codex-fixture"
    try:
        if path.is_symlink() or path.is_junction():
            raise OSError("linked marker")
        with path.open("rb") as stream:
            marker = stream.read(len(SYNTHETIC_MARKER) + 1)
    except OSError as exc:
        raise DataValidationError(
            "synthetic_fixture_marker_required",
            "Synthetic Codex inventory requires its exact fixture marker.",
        ) from exc
    if marker != SYNTHETIC_MARKER:
        raise DataValidationError(
            "synthetic_fixture_marker_required",
            "Synthetic Codex inventory requires its exact fixture marker.",
        )


def _entry(item: DiscoveredCodexFile, limits: CodexInventoryLimits) -> CodexInventoryEntry:
    state = inspect_first_record(item, limits.max_first_record_bytes)
    locator = item.relative.as_posix()
    return CodexInventoryEntry(
        source_key=sha256_text(f"codex-local:{item.partition}:{locator}"),
        partition=item.partition,
        file_bytes=item.file_bytes,
        observed_month=_observed_month(locator),
        first_record_state=state,
    )


def _observed_month(locator: str) -> str | None:
    match = re.search(r"(?:^|/)(20\d{2})/(0[1-9]|1[0-2])(?:/|$)", locator)
    if match is None:
        match = re.search(r"rollout-(20\d{2})-(0[1-9]|1[0-2])-", locator)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def _build_manifest(
    entries: tuple[CodexInventoryEntry, ...],
    *,
    ignored_noncanonical: int,
    synthetic: bool,
    record_id: UUID | None,
    created_at: datetime | None,
) -> CodexMetadataInventory:
    months: dict[str, list[int]] = {}
    for entry in entries:
        if entry.observed_month:
            aggregate = months.setdefault(entry.observed_month, [0, 0])
            aggregate[0] += 1
            aggregate[1] += entry.file_bytes
    monthly = tuple(
        CodexMonthSummary(month=month, file_count=values[0], total_bytes=values[1])
        for month, values in sorted(months.items())
    )
    snapshot = _metadata_snapshot(entries, ignored_noncanonical)
    draft = CodexMetadataInventory(
        record_id=record_id or new_id(),
        created_at=created_at or utc_now(),
        parser_version=CODEX_METADATA_PARSER_VERSION,
        source_data_class=DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS,
        synthetic=synthetic,
        entries=entries,
        entry_count=len(entries),
        total_bytes=sum(item.file_bytes for item in entries),
        ignored_noncanonical_file_count=ignored_noncanonical,
        partition_counts=dict(sorted(Counter(item.partition for item in entries).items())),
        state_counts=dict(sorted(Counter(item.first_record_state for item in entries).items())),
        monthly=monthly,
        metadata_snapshot_sha256=snapshot,
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"manifest_sha256"}))
    return draft.model_copy(update={"manifest_sha256": digest})


def verify_codex_metadata_inventory(manifest: CodexMetadataInventory) -> None:
    try:
        safe = CodexMetadataInventory.model_validate(manifest.model_dump(mode="python"))
    except ValueError as exc:
        raise DataValidationError(
            "codex_manifest_invalid", "Codex metadata manifest failed strict validation."
        ) from exc
    snapshot = _metadata_snapshot(safe.entries, safe.ignored_noncanonical_file_count)
    digest = canonical_sha256(safe.model_dump(mode="json", exclude={"manifest_sha256"}))
    if snapshot != safe.metadata_snapshot_sha256 or digest != safe.manifest_sha256:
        raise DataValidationError(
            "codex_manifest_digest_mismatch", "Codex metadata manifest checksum check failed."
        )


def _metadata_snapshot(entries: tuple[CodexInventoryEntry, ...], ignored: int) -> str:
    return canonical_sha256(
        {
            "entries": [item.model_dump(mode="json") for item in entries],
            "ignored_noncanonical_file_count": ignored,
        }
    )
