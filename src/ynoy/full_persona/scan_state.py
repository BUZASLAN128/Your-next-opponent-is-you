from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, BinaryIO, cast
from uuid import NAMESPACE_URL, uuid5

from ynoy.corpus.codex_normalizer import normalize_codex_record
from ynoy.corpus.codex_normalizer_types import CodexFileBinding, CodexParserState
from ynoy.errors import DataValidationError
from ynoy.full_persona.evidence import EvidenceContext, evidence_from_event
from ynoy.full_persona.records import iter_bounded_jsonl_records
from ynoy.full_persona.shards import ShardBuffer
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import seal_full_corpus_head
from ynoy.models import DataClass
from ynoy.models.full_persona import (
    FullCorpusFileReceipt,
    FullCorpusHead,
    FullCorpusManifest,
    FullCorpusShardReceipt,
    FullCorpusSource,
)
from ynoy.util import canonical_sha256


@dataclass(slots=True)
class ScanState:
    manifest: FullCorpusManifest
    source: FullCorpusSource
    head: FullCorpusHead
    parser: CodexParserState
    context: EvidenceContext
    offset: int
    lines: int
    invocation_bytes: int = 0
    records: int = 0
    evidence: int = 0
    quarantined: int = 0
    exclusions: Counter[str] | None = None

    def __post_init__(self) -> None:
        self.records = self.head.current_file_record_count
        self.evidence = self.head.current_file_evidence_count
        self.quarantined = self.head.current_file_quarantined_count
        self.exclusions = Counter(self.head.current_file_exclusion_counts)


def consume_records(
    store: FullPersonaStore,
    state: ScanState,
    buffer: ShardBuffer,
    stream: BinaryIO,
    budget: int | None,
) -> ShardBuffer:
    limits = state.manifest.limits
    records = iter_bounded_jsonl_records(
        stream,
        start_offset=state.offset,
        completed_lines=state.lines,
        max_line_bytes=limits.max_line_bytes,
        max_wire_record_bytes=limits.max_wire_record_bytes,
    )
    binding = _binding(state)
    for raw in records:
        if budget is not None and state.invocation_bytes + raw.byte_length > budget:
            if state.invocation_bytes == 0:
                raise DataValidationError(
                    "full_persona_scan_budget_too_small",
                    "The scan budget is smaller than the next bounded JSONL record.",
                    details={"minimum_bytes": raw.byte_length},
                )
            break
        if _near_full(buffer):
            state.head = commit_progress(store, state, buffer)
            buffer = ShardBuffer(store, state.manifest.run_id, state.source, state.manifest.limits)
        event = normalize_codex_record(raw, state.parser, binding)
        evidence, exclusion = evidence_from_event(event, state.source, state.context.values, limits)
        _record_event(state, raw.byte_start + raw.byte_length, raw.line_number, raw.byte_length)
        if evidence is None:
            _exclude(state, exclusion or "other")
        else:
            encoded = buffer.encoded(evidence)
            if buffer.can_accept(encoded):
                buffer.write(evidence, encoded)
                state.evidence += 1
            else:
                _exclude(state, "evidence_exceeds_shard")
        state.context.observe(event)
        if state.offset - state.head.next_byte_offset >= limits.max_checkpoint_input_bytes:
            break
    return buffer


def commit_progress(
    store: FullPersonaStore, state: ScanState, buffer: ShardBuffer
) -> FullCorpusHead:
    revision = state.head.revision + 1
    receipt = buffer.finish(revision)
    next_head = _next_head(state, receipt, complete_file=False)
    return store.commit_revision(
        state.head,
        next_head,
        staging_shard=buffer.path if receipt is not None else None,
        shard_receipt=receipt,
    )


def commit_file(store: FullPersonaStore, state: ScanState, buffer: ShardBuffer) -> FullCorpusHead:
    revision = state.head.revision + 1
    shard = buffer.finish(revision)
    file_receipt = _seal_file_receipt(state)
    next_head = _next_head(state, shard, complete_file=True)
    return store.commit_revision(
        state.head,
        next_head,
        staging_shard=buffer.path if shard is not None else None,
        shard_receipt=shard,
        file_receipts=(file_receipt,),
    )


def exclude_file_remainder(state: ScanState, error: DataValidationError) -> None:
    consumed = error.details.get("consumed_bytes", 0)
    if not isinstance(consumed, int) or consumed < 1:
        raise error
    state.records += 1
    _exclude(state, "wire_record_remainder_excluded", count_record=False)
    state.invocation_bytes += state.source.file_bytes - state.offset
    state.offset = state.source.file_bytes
    state.lines += 1


def _binding(state: ScanState) -> CodexFileBinding:
    return CodexFileBinding(
        snapshot_id=uuid5(NAMESPACE_URL, state.manifest.run_id),
        source_key=state.source.source_key,
        blob_sha256=state.source.blob_sha256,
        data_class=(
            DataClass.PUBLIC_SYNTHETIC if state.manifest.synthetic else DataClass.RAW_CORPUS
        ),
        synthetic=state.manifest.synthetic,
    )


def _record_event(state: ScanState, offset: int, line: int, byte_length: int) -> None:
    state.records += 1
    state.invocation_bytes += byte_length
    state.offset = offset
    state.lines = line


def _exclude(state: ScanState, reason: str, *, count_record: bool = True) -> None:
    del count_record
    state.quarantined += 1
    assert state.exclusions is not None
    state.exclusions[reason] += 1


def _near_full(buffer: ShardBuffer) -> bool:
    bound = buffer.limits.max_evidence_bytes + buffer.limits.max_context_bytes + 64 * 1024
    return buffer.record_count >= buffer.limits.max_shard_records or (
        buffer.record_count > 0
        and buffer.uncompressed_bytes + bound > buffer.limits.max_shard_uncompressed_bytes
    )


def _next_head(
    state: ScanState,
    shard: FullCorpusShardReceipt | None,
    *,
    complete_file: bool,
) -> FullCorpusHead:
    global_exclusions = Counter(state.head.exclusion_counts)
    assert state.exclusions is not None
    previous_file = Counter(state.head.current_file_exclusion_counts)
    global_exclusions.update(state.exclusions - previous_file)
    shard_bytes = 0 if shard is None else shard.compressed_bytes
    processed_delta = state.offset - state.head.next_byte_offset
    payload = {
        "run_id": state.head.run_id,
        "manifest_sha256": state.head.manifest_sha256,
        "revision": state.head.revision + 1,
        "status": "scanning",
        "file_index": state.head.file_index + int(complete_file),
        "next_byte_offset": 0 if complete_file else state.offset,
        "completed_lines": 0 if complete_file else state.lines,
        "parser_state": {} if complete_file else state.parser.to_payload(),
        "context": () if complete_file else state.context.values,
        "processed_input_bytes": state.head.processed_input_bytes + processed_delta,
        "processed_record_count": state.head.processed_record_count
        + state.records
        - state.head.current_file_record_count,
        "evidence_count": state.head.evidence_count
        + state.evidence
        - state.head.current_file_evidence_count,
        "quarantined_count": state.head.quarantined_count
        + state.quarantined
        - state.head.current_file_quarantined_count,
        "current_file_record_count": 0 if complete_file else state.records,
        "current_file_evidence_count": 0 if complete_file else state.evidence,
        "current_file_quarantined_count": 0 if complete_file else state.quarantined,
        "current_file_exclusion_counts": (
            {} if complete_file else dict(sorted(state.exclusions.items()))
        ),
        "shard_count": state.head.shard_count + int(shard is not None),
        "output_bytes": state.head.output_bytes + shard_bytes + 8192,
        "exclusion_counts": dict(sorted(global_exclusions.items())),
        "previous_head_sha256": state.head.head_sha256,
        "last_shard_sha256": (
            state.head.last_shard_sha256 if shard is None else shard.content_sha256
        ),
    }
    return seal_full_corpus_head(payload)


def _seal_file_receipt(state: ScanState) -> FullCorpusFileReceipt:
    assert state.exclusions is not None
    payload = {
        "run_id": state.manifest.run_id,
        "file_index": state.head.file_index,
        "source_key": state.source.source_key,
        "source_receipt": state.source.source_receipt,
        "blob_sha256": state.source.blob_sha256,
        "processed_bytes": state.source.file_bytes,
        "record_count": state.records,
        "evidence_count": state.evidence,
        "quarantined_count": state.quarantined,
        "exclusion_counts": dict(sorted(state.exclusions.items())),
        "status": (
            "remainder_excluded"
            if state.exclusions.get("wire_record_remainder_excluded")
            else "complete"
        ),
    }
    draft = cast(Any, FullCorpusFileReceipt).model_construct(**payload, receipt_sha256="0" * 64)
    return FullCorpusFileReceipt.model_validate(
        {
            **payload,
            "receipt_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"receipt_sha256"})
            ),
        }
    )
