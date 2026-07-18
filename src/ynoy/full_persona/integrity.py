from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import (
    FullCorpusFileReceipt,
    FullCorpusHead,
    FullCorpusManifest,
    FullCorpusShardReceipt,
)
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.util import sha256_file

_CONTROL_BYTES = 16 * 1024**2


def verify_committed_run(
    store: FullPersonaStore, manifest: FullCorpusManifest, head: FullCorpusHead
) -> None:
    """Verify every committed control receipt and shard before resume or status."""
    run = store.run_path(manifest.run_id)
    _verify_head_chain(run, head)
    _verify_shards(run, manifest, head)
    _verify_file_receipts(run, manifest, head)


def _verify_head_chain(run: Path, expected: FullCorpusHead) -> None:
    root = run / "heads"
    _require_directory(root)
    previous: FullCorpusHead | None = None
    for revision in range(expected.revision + 1):
        head = _read_model(root / f"{revision:08d}.json", FullCorpusHead)
        if head.revision != revision:
            _integrity_error("head revision does not match its immutable path")
        if previous is None:
            if head.previous_head_sha256 is not None:
                _integrity_error("initial head unexpectedly has a parent")
        elif head.previous_head_sha256 != previous.head_sha256:
            _integrity_error("head parent chain is broken")
        previous = head
    if _file_count(root, "*.json") != expected.revision + 1:
        _integrity_error("head directory contains an unrecognized revision")
    if previous is None or previous.head_sha256 != expected.head_sha256:
        _integrity_error("head pointer does not match the immutable chain")


def _verify_shards(run: Path, manifest: FullCorpusManifest, head: FullCorpusHead) -> None:
    root = run / "shards"
    _require_directory(root)
    paths = tuple(sorted(root.glob("*.jsonl.gz")))
    receipts = tuple(sorted(root.glob("*.receipt.json")))
    if len(paths) != head.shard_count or len(receipts) != head.shard_count:
        _integrity_error("shard inventory does not match the committed head")
    evidence_count = 0
    last_digest: str | None = None
    valid_sources = {item.source_key for item in manifest.files}
    for path in paths:
        require_regular_file(path)
        receipt_path = path.with_suffix(".receipt.json")
        receipt = _read_model(receipt_path, FullCorpusShardReceipt)
        expected_relative = path.relative_to(run).as_posix()
        if receipt.relative_path != expected_relative or receipt.source_key not in valid_sources:
            _integrity_error("shard receipt has an invalid source or path binding")
        if path.stat().st_size != receipt.compressed_bytes:
            _integrity_error("shard byte count does not match its receipt")
        digest = sha256_file(path)
        if digest != receipt.content_sha256:
            _integrity_error("shard content failed its committed hash")
        evidence_count += receipt.evidence_count
        last_digest = digest
    if evidence_count != head.evidence_count or last_digest != head.last_shard_sha256:
        _integrity_error("shard evidence or tail hash does not match the head")


def _verify_file_receipts(run: Path, manifest: FullCorpusManifest, head: FullCorpusHead) -> None:
    root = run / "files"
    _require_directory(root)
    if _file_count(root, "*.json") != head.file_index:
        _integrity_error("completed-file receipt inventory does not match the head")
    records = evidence = quarantined = processed = 0
    exclusions: Counter[str] = Counter()
    for index in range(head.file_index):
        receipt = _read_model(root / f"{index:08d}.json", FullCorpusFileReceipt)
        source = manifest.files[index]
        if (
            receipt.file_index != index
            or receipt.source_key != source.source_key
            or receipt.source_receipt != source.source_receipt
            or receipt.blob_sha256 != source.blob_sha256
            or receipt.processed_bytes != source.file_bytes
        ):
            _integrity_error("completed-file receipt does not match its frozen source")
        records += receipt.record_count
        evidence += receipt.evidence_count
        quarantined += receipt.quarantined_count
        processed += receipt.processed_bytes
        exclusions.update(receipt.exclusion_counts)
    records += head.current_file_record_count
    evidence += head.current_file_evidence_count
    quarantined += head.current_file_quarantined_count
    processed += head.next_byte_offset
    exclusions.update(head.current_file_exclusion_counts)
    if (records, evidence, quarantined, processed) != (
        head.processed_record_count,
        head.evidence_count,
        head.quarantined_count,
        head.processed_input_bytes,
    ):
        _integrity_error("file receipt totals do not reconcile to the head")
    if dict(sorted(exclusions.items())) != head.exclusion_counts:
        _integrity_error("file exclusion totals do not reconcile to the head")


def _read_model[ModelT](path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate_json(_read_bounded(path))  # type: ignore[attr-defined,no-any-return]
    except (OSError, ValidationError, ValueError) as exc:
        raise DataValidationError(
            "full_persona_integrity_invalid", "A committed full-persona receipt is invalid."
        ) from exc


def _read_bounded(path: Path) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        value = stream.read(_CONTROL_BYTES + 1)
    if len(value) > _CONTROL_BYTES:
        _integrity_error("a committed control receipt is oversized")
    return value


def _file_count(root: Path, pattern: str) -> int:
    count = 0
    for path in root.glob(pattern):
        require_regular_file(path)
        count += 1
    return count


def _require_directory(path: Path) -> None:
    reject_link_if_present(path)
    if not path.is_dir():
        _integrity_error("a committed artifact directory is missing")


def _integrity_error(reason: str) -> None:
    raise DataValidationError(
        "full_persona_integrity_invalid",
        "The committed full-persona run failed integrity verification.",
        details={"reason": reason},
    )
