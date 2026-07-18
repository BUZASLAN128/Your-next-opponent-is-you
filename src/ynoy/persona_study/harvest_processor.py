from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ynoy.corpus.codex import assert_synthetic_codex_root
from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.errors import DataValidationError
from ynoy.models.persona_harvest import (
    HarvestCheckpoint,
    HarvestFileCursor,
    HarvestManifest,
    HarvestStatus,
)
from ynoy.persona_study.harvest_contract import (
    seal_harvest_checkpoint,
    seal_harvest_cursor,
)
from ynoy.persona_study.harvest_discovery import (
    discover_harvest_batch,
    harvest_file_sort_key,
)
from ynoy.persona_study.harvest_file_processor import (
    HarvestCheckpointState,
    process_harvest_file,
    verify_harvest_anchor,
)
from ynoy.persona_study.harvest_reservoir import HarvestReservoir

Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class HarvestProcessingResult:
    checkpoint: HarvestCheckpoint
    source_dependencies: tuple[str, ...]
    metadata_entries_scanned: int


def process_harvest_checkpoint(
    root: Path,
    manifest: HarvestManifest,
    previous: HarvestCheckpoint | None = None,
    *,
    clock: Clock = time.monotonic,
) -> HarvestProcessingResult:
    """Stream one bounded checkpoint and retain only a fixed candidate reservoir."""
    _verify_previous(manifest, previous)
    if manifest.synthetic:
        assert_synthetic_codex_root(root)
    prior_cursor = None if previous is None else previous.cursor.last_file
    batch = discover_harvest_batch(
        root,
        manifest.limits,
        stable_before_ns=manifest.stable_before_ns,
        holdout_boundary_ns=manifest.holdout_boundary_session_start_ns,
        previous=prior_cursor,
    )
    verify_harvest_anchor(prior_cursor, batch.anchor)
    initial = () if previous is None else previous.candidates
    state = HarvestCheckpointState(
        HarvestReservoir(
            manifest.limits.max_reservoir,
            manifest.selector_config_sha256,
            initial,
        ),
        Counter(),
        clock(),
    )
    last_file, dependencies = _process_batch(
        batch.files,
        manifest,
        prior_cursor,
        state,
        clock,
        {item.source_receipt for item in initial},
    )
    complete = not state.stopped and not batch.has_more and _batch_consumed(batch.files, last_file)
    checkpoint = _build_checkpoint(manifest, previous, last_file, state, complete)
    dependencies.add(manifest.holdout_freeze_sha256)
    if last_file is not None:
        dependencies.add(last_file.source_receipt)
    return HarvestProcessingResult(
        checkpoint,
        tuple(sorted(dependencies)),
        batch.entries_scanned,
    )


def _process_batch(
    files: tuple[DiscoveredCodexFile, ...],
    manifest: HarvestManifest,
    prior_cursor: HarvestFileCursor | None,
    state: HarvestCheckpointState,
    clock: Clock,
    dependencies: set[str],
) -> tuple[HarvestFileCursor | None, set[str]]:
    last_file = prior_cursor
    for item in files:
        if _checkpoint_limit_reached(state, manifest, clock):
            break
        progress = process_harvest_file(item, manifest, prior_cursor, state, clock)
        last_file = progress.cursor
        dependencies.add(progress.source_dependency)
        prior_cursor = None
        if not progress.cursor.complete:
            state.stopped = True
            break
    return last_file, dependencies


def _build_checkpoint(
    manifest: HarvestManifest,
    previous: HarvestCheckpoint | None,
    last_file: HarvestFileCursor | None,
    state: HarvestCheckpointState,
    complete: bool,
) -> HarvestCheckpoint:
    revision = 1 if previous is None else previous.cursor.revision + 1
    cursor = seal_harvest_cursor(
        run_id=manifest.run_id,
        source_study_id=manifest.source_study_id,
        freeze_sha256=manifest.holdout_freeze_sha256,
        stable_before_ns=manifest.stable_before_ns,
        selector_config_sha256=manifest.selector_config_sha256,
        revision=revision,
        last_file=last_file,
        complete=complete,
    )
    return seal_harvest_checkpoint(
        cursor=cursor,
        candidates=state.reservoir.candidates,
        exclusion_counts=dict(state.exclusions),
        input_bytes=state.input_bytes,
        record_count=state.records,
        event_count=state.events,
        file_count=state.files,
        status=_checkpoint_status(complete, len(state.reservoir.candidates)),
    )


def _verify_previous(manifest: HarvestManifest, previous: HarvestCheckpoint | None) -> None:
    if previous is None:
        return
    cursor = previous.cursor
    if cursor.status == "complete":
        raise DataValidationError("codex_harvest_complete", "The harvest cursor is complete.")
    if cursor.revision >= manifest.limits.max_checkpoints:
        raise DataValidationError(
            "codex_harvest_checkpoint_limit", "The harvest reached its checkpoint limit."
        )
    expected = (
        manifest.run_id,
        manifest.source_study_id,
        manifest.holdout_freeze_sha256,
        manifest.stable_before_ns,
        manifest.selector_config_sha256,
    )
    actual = (
        cursor.run_id,
        cursor.source_study_id,
        cursor.holdout_freeze_sha256,
        cursor.stable_before_ns,
        cursor.selector_config_sha256,
    )
    if actual != expected:
        raise DataValidationError(
            "codex_harvest_cursor_binding_invalid", "The harvest cursor binding is stale."
        )


def _checkpoint_limit_reached(
    state: HarvestCheckpointState,
    manifest: HarvestManifest,
    clock: Clock,
) -> bool:
    limits = manifest.limits
    reached = (
        state.files >= limits.max_files
        or state.records >= limits.max_records
        or state.events >= limits.max_events
        or clock() - state.started >= limits.max_wall_seconds
    )
    state.stopped = state.stopped or reached
    return reached


def _batch_consumed(
    files: tuple[DiscoveredCodexFile, ...], last_file: HarvestFileCursor | None
) -> bool:
    if not files:
        return True
    return (
        last_file is not None
        and last_file.complete
        and last_file.sort_key == harvest_file_sort_key(files[-1])
    )


def _checkpoint_status(complete: bool, candidate_count: int) -> HarvestStatus:
    if complete:
        return "complete" if candidate_count >= 12 else "complete_insufficient"
    return "audit_ready" if candidate_count >= 12 else "partial"
