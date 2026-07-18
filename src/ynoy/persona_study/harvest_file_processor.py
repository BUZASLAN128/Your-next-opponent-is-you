from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO
from uuid import NAMESPACE_URL, uuid5

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.corpus.codex_normalizer import normalize_codex_record
from ynoy.corpus.codex_normalizer_types import CodexFileBinding, CodexParserState
from ynoy.corpus.codex_raw_records import iter_jsonl_records
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.models.persona_harvest import HarvestFileCursor, HarvestManifest
from ynoy.persona_study.harvest_discovery import harvest_file_sort_key
from ynoy.persona_study.harvest_events import HarvestContextBuffer, offer_harvest_event
from ynoy.persona_study.harvest_reservoir import HarvestReservoir
from ynoy.persona_study.lineage import file_receipt
from ynoy.util import canonical_sha256

Clock = Callable[[], float]


@dataclass(slots=True)
class HarvestCheckpointState:
    reservoir: HarvestReservoir
    exclusions: Counter[str]
    started: float
    input_bytes: int = 0
    records: int = 0
    events: int = 0
    files: int = 0
    stopped: bool = False


@dataclass(frozen=True, slots=True)
class HarvestFileProgress:
    cursor: HarvestFileCursor
    source_dependency: str


def verify_harvest_anchor(
    previous: HarvestFileCursor | None, anchor: DiscoveredCodexFile | None
) -> None:
    if previous is None:
        return
    if anchor is None or _metadata_receipt(anchor) != _cursor_metadata_receipt(previous):
        raise DataValidationError(
            "codex_harvest_source_changed", "The harvest source anchor changed after checkpoint."
        )
    if digest_harvest_file(anchor) != previous.blob_sha256:
        raise DataValidationError(
            "codex_harvest_source_changed", "The harvest source content changed after checkpoint."
        )


def process_harvest_file(
    item: DiscoveredCodexFile,
    manifest: HarvestManifest,
    previous: HarvestFileCursor | None,
    checkpoint: HarvestCheckpointState,
    clock: Clock,
) -> HarvestFileProgress:
    blob_sha256 = digest_harvest_file(item)
    source_receipt = file_receipt(item)
    start_offset, completed_lines = _resume_position(item, previous, blob_sha256)
    binding = _binding(item, manifest, blob_sha256)
    parser = CodexParserState()
    context = HarvestContextBuffer(manifest)
    with open_stable_codex_file(item) as stream:
        _replay_prefix(stream, binding, parser, context, manifest, start_offset, completed_lines)
        cursor = _consume_new_records(
            stream,
            item,
            binding,
            parser,
            context,
            manifest,
            checkpoint,
            source_receipt,
            start_offset,
            completed_lines,
            clock,
        )
    checkpoint.files += int(cursor.complete)
    return HarvestFileProgress(cursor, source_receipt)


def _replay_prefix(
    stream: BinaryIO,
    binding: CodexFileBinding,
    parser: CodexParserState,
    context: HarvestContextBuffer,
    manifest: HarvestManifest,
    target_offset: int,
    completed_lines: int,
) -> None:
    if target_offset == 0:
        return
    observed_offset = observed_lines = 0
    for raw in iter_jsonl_records(stream, max_line_bytes=manifest.limits.max_line_bytes):
        if raw.byte_start >= target_offset:
            break
        event = normalize_codex_record(raw, parser, binding)
        context.observe(event)
        observed_offset = raw.byte_start + raw.byte_length
        observed_lines = raw.line_number
    if observed_offset != target_offset or observed_lines != completed_lines:
        raise DataValidationError(
            "codex_harvest_cursor_offset_invalid", "The harvest cursor is not a record boundary."
        )


def _consume_new_records(
    stream: BinaryIO,
    item: DiscoveredCodexFile,
    binding: CodexFileBinding,
    parser: CodexParserState,
    context: HarvestContextBuffer,
    manifest: HarvestManifest,
    checkpoint: HarvestCheckpointState,
    source_receipt: str,
    start_offset: int,
    completed_lines: int,
    clock: Clock,
) -> HarvestFileCursor:
    offset, lines = start_offset, completed_lines
    complete = True
    records = iter_jsonl_records(
        stream,
        start_offset=start_offset,
        completed_lines=completed_lines,
        max_line_bytes=manifest.limits.max_line_bytes,
    )
    for raw in records:
        if _record_limit_reached(checkpoint, manifest, raw.byte_length, clock):
            complete = False
            break
        event = normalize_codex_record(raw, parser, binding)
        offer_harvest_event(
            checkpoint.reservoir,
            checkpoint.exclusions,
            event,
            item,
            source_receipt,
            context,
            manifest,
        )
        context.observe(event)
        checkpoint.records += 1
        checkpoint.events += 1
        checkpoint.input_bytes += raw.byte_length
        offset = raw.byte_start + raw.byte_length
        lines = raw.line_number
    if complete:
        offset = item.file_bytes
    return _file_cursor(item, source_receipt, binding.blob_sha256, offset, lines, complete)


def _record_limit_reached(
    checkpoint: HarvestCheckpointState,
    manifest: HarvestManifest,
    next_bytes: int,
    clock: Clock,
) -> bool:
    limits = manifest.limits
    reached = (
        checkpoint.input_bytes + next_bytes > limits.max_total_input_bytes
        or checkpoint.records >= limits.max_records
        or checkpoint.events >= limits.max_events
        or clock() - checkpoint.started >= limits.max_wall_seconds
    )
    checkpoint.stopped = checkpoint.stopped or reached
    return reached


def _binding(
    item: DiscoveredCodexFile, manifest: HarvestManifest, blob_sha256: str
) -> CodexFileBinding:
    return CodexFileBinding(
        snapshot_id=uuid5(NAMESPACE_URL, manifest.source_study_id),
        source_key=canonical_sha256((item.partition, item.relative.as_posix())),
        blob_sha256=blob_sha256,
        data_class=manifest.source_data_class,
        synthetic=manifest.synthetic,
    )


def _resume_position(
    item: DiscoveredCodexFile,
    previous: HarvestFileCursor | None,
    blob_sha256: str,
) -> tuple[int, int]:
    if previous is None or previous.complete or harvest_file_sort_key(item) != previous.sort_key:
        return 0, 0
    if (file_receipt(item), blob_sha256) != (
        previous.source_receipt,
        previous.blob_sha256,
    ):
        raise DataValidationError(
            "codex_harvest_source_changed", "The resumed harvest file changed."
        )
    return previous.next_byte_offset, previous.completed_lines


def _file_cursor(
    item: DiscoveredCodexFile,
    source_receipt: str,
    blob_sha256: str,
    offset: int,
    lines: int,
    complete: bool,
) -> HarvestFileCursor:
    return HarvestFileCursor(
        partition=item.partition,
        relative_locator=item.relative.as_posix(),
        sort_key=harvest_file_sort_key(item),
        source_key=canonical_sha256((item.partition, item.relative.as_posix())),
        source_receipt=source_receipt,
        blob_sha256=blob_sha256,
        file_bytes=item.file_bytes,
        modified_ns=item.modified_ns,
        device=item.device,
        inode=item.inode,
        next_byte_offset=offset,
        completed_lines=lines,
        complete=complete,
    )


def digest_harvest_file(item: DiscoveredCodexFile) -> str:
    digest = hashlib.sha256()
    with open_stable_codex_file(item) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_receipt(item: DiscoveredCodexFile) -> tuple[object, ...]:
    return (
        item.partition,
        item.relative.as_posix(),
        item.file_bytes,
        item.modified_ns,
        item.device,
        item.inode,
    )


def _cursor_metadata_receipt(cursor: HarvestFileCursor) -> tuple[object, ...]:
    return (
        cursor.partition,
        cursor.relative_locator,
        cursor.file_bytes,
        cursor.modified_ns,
        cursor.device,
        cursor.inode,
    )
