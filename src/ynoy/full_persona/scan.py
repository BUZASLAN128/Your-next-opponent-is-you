from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from ynoy.corpus.codex import assert_synthetic_codex_root, codex_source_key
from ynoy.corpus.codex_discovery import (
    CodexInventoryLimits,
    DiscoveredCodexFile,
    discover_codex_sessions,
    resolve_codex_root,
)
from ynoy.corpus.codex_normalizer_types import CodexParserState
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.full_persona.evidence import EvidenceContext
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.scan_state import (
    ScanState,
    commit_file,
    commit_progress,
    consume_records,
    exclude_file_remainder,
)
from ynoy.full_persona.shards import ShardBuffer
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import seal_full_corpus_head
from ynoy.models.full_persona import FullCorpusHead, FullCorpusManifest, FullCorpusSource
from ynoy.persona_study.lineage import session_start_ns
from ynoy.util import utc_now


def scan_full_corpus(
    source_root: Path,
    private_root: Path,
    run_id: str,
    *,
    synthetic: bool,
    max_input_bytes: int | None = None,
) -> FullCorpusHead:
    """Resume a source-bound scan while keeping one record and one shard in memory."""
    if max_input_bytes is not None and max_input_bytes < 1:
        raise DataValidationError(
            "full_persona_scan_budget_invalid", "The scan byte budget must be positive."
        )
    store = FullPersonaStore(private_root, synthetic=synthetic)
    with store.lock(run_id):
        manifest = store.read_manifest(run_id)
        if manifest.expires_at <= utc_now():
            raise DataValidationError(
                "full_persona_run_expired", "The private full-persona run has expired."
            )
        head = store.read_head(run_id)
        verify_committed_run(store, manifest, head)
        if head.status == "complete":
            return head
        current = _verify_source_universe(source_root, manifest)
        consumed = 0
        while head.file_index < len(manifest.files):
            remaining = None if max_input_bytes is None else max_input_bytes - consumed
            if remaining is not None and remaining <= 0:
                break
            source = manifest.files[head.file_index]
            head, used = _scan_source(store, manifest, head, current[source.source_key], remaining)
            consumed += used
            if used == 0 or (head.file_index < len(manifest.files) and head.next_byte_offset > 0):
                break
        if head.file_index == len(manifest.files) and head.status != "complete":
            _verify_all_source_digests(current, manifest)
            verify_committed_run(store, manifest, head)
            head = _commit_complete(store, manifest, head)
            verify_committed_run(store, manifest, head)
        return head


def _verify_source_universe(
    source_root: Path, manifest: FullCorpusManifest
) -> dict[str, DiscoveredCodexFile]:
    root = resolve_codex_root(source_root)
    if manifest.synthetic:
        assert_synthetic_codex_root(root)
    discovery = discover_codex_sessions(
        root,
        CodexInventoryLimits(
            max_files=manifest.limits.max_manifest_files, max_entries=200_000, max_depth=8
        ),
    )
    eligible = tuple(
        item
        for item in discovery.files
        if item.file_bytes > 0
        and session_start_ns(item) < manifest.holdout_boundary_session_start_ns
    )
    current = {codex_source_key(item): item for item in eligible}
    if set(current) != {item.source_key for item in manifest.files}:
        raise DataValidationError(
            "full_persona_source_universe_changed",
            "The canonical pre-holdout source universe changed after freeze.",
        )
    for source in manifest.files:
        if _metadata_tuple(current[source.source_key]) != _source_tuple(source):
            raise DataValidationError(
                "full_persona_source_changed", "A frozen full-persona source changed."
            )
    return current


def _metadata_tuple(item: DiscoveredCodexFile) -> tuple[object, ...]:
    return (
        item.partition,
        item.relative.as_posix(),
        item.file_bytes,
        item.modified_ns,
        item.device,
        item.inode,
    )


def _source_tuple(source: FullCorpusSource) -> tuple[object, ...]:
    return (
        source.partition,
        source.relative_locator,
        source.file_bytes,
        source.modified_ns,
        source.device,
        source.inode,
    )


def _scan_source(
    store: FullPersonaStore,
    manifest: FullCorpusManifest,
    head: FullCorpusHead,
    item: DiscoveredCodexFile,
    budget: int | None,
) -> tuple[FullCorpusHead, int]:
    source = manifest.files[head.file_index]
    state = ScanState(
        manifest,
        source,
        head,
        CodexParserState.from_payload(head.parser_state),
        EvidenceContext(manifest.limits, head.context),
        head.next_byte_offset,
        head.completed_lines,
    )
    with open_stable_codex_file(item) as stream:
        _verify_opened_digest(stream, source)
        _consume_open_source(store, state, stream, budget)
    return state.head, state.invocation_bytes


def _consume_open_source(
    store: FullPersonaStore,
    state: ScanState,
    stream: BinaryIO,
    budget: int | None,
) -> None:
    while state.offset < state.source.file_bytes:
        before = state.offset
        buffer = ShardBuffer(store, state.manifest.run_id, state.source, state.manifest.limits)
        try:
            buffer = consume_records(store, state, buffer, stream, budget)
        except DataValidationError as exc:
            if exc.code != "full_persona_wire_record_limit":
                buffer.abort()
                raise
            exclude_file_remainder(state, exc)
        if state.offset == before:
            buffer.abort()
            return
        if state.offset == state.source.file_bytes:
            state.head = commit_file(store, state, buffer)
            return
        state.head = commit_progress(store, state, buffer)
        if budget is not None and state.invocation_bytes >= budget:
            return


def _verify_opened_digest(stream: BinaryIO, source: FullCorpusSource) -> None:
    digest = hashlib.sha256()
    stream.seek(0)
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    if digest.hexdigest() != source.blob_sha256:
        raise DataValidationError(
            "full_persona_source_changed", "A frozen full-persona source digest changed."
        )
    stream.seek(0)


def _verify_all_source_digests(
    current: dict[str, DiscoveredCodexFile], manifest: FullCorpusManifest
) -> None:
    for source in manifest.files:
        with open_stable_codex_file(current[source.source_key]) as stream:
            _verify_opened_digest(stream, source)


def _commit_complete(
    store: FullPersonaStore, manifest: FullCorpusManifest, head: FullCorpusHead
) -> FullCorpusHead:
    payload = head.model_dump(mode="python", exclude={"head_sha256"})
    payload.update(
        revision=head.revision + 1,
        status="complete",
        previous_head_sha256=head.head_sha256,
        output_bytes=head.output_bytes + 4096,
    )
    complete = seal_full_corpus_head(payload)
    if (
        complete.file_index != manifest.expected_file_count
        or complete.processed_input_bytes != manifest.expected_input_bytes
    ):
        raise DataValidationError(
            "full_persona_completion_reconciliation_failed",
            "Full-persona completion counts do not match the frozen manifest.",
        )
    return store.commit_revision(head, complete)
