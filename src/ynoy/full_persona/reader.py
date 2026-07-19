from __future__ import annotations

import gzip
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import BinaryIO, NoReturn, cast

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.records import iter_bounded_jsonl_records
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import (
    FullCorpusEvidence,
    FullCorpusHead,
    FullCorpusManifest,
    FullCorpusShardReceipt,
)
from ynoy.persona_study.storage_paths import require_regular_file

_CONTROL_BYTES = 16 * 1024**2


def iter_verified_evidence(
    store: FullPersonaStore,
    manifest: FullCorpusManifest,
    head: FullCorpusHead,
) -> Iterator[FullCorpusEvidence]:
    """Yield complete evidence shards sequentially after binding the live pointer."""
    current = store.read_head(manifest.run_id)
    if current.head_sha256 != head.head_sha256 or current.status != "complete":
        raise DataValidationError(
            "persona_pack_source_not_complete",
            "A persona pack requires the current completed corpus head.",
        )
    verify_committed_run(store, manifest, current)
    total = 0
    for shard_path in store.iter_shard_paths(manifest.run_id):
        receipt = _read_receipt(shard_path.with_suffix(".receipt.json"))
        count = yield from _iter_shard(shard_path, receipt, manifest)
        total += count
    if total != current.evidence_count:
        raise DataValidationError(
            "persona_pack_evidence_count_mismatch",
            "Persona evidence did not reconcile to the completed corpus head.",
        )


def _iter_shard(
    path: Path,
    receipt: FullCorpusShardReceipt,
    manifest: FullCorpusManifest,
) -> Generator[FullCorpusEvidence, None, int]:
    expected_path = path.relative_to(path.parents[1]).as_posix()
    if receipt.run_id != manifest.run_id or receipt.relative_path != expected_path:
        _reader_error("shard receipt is bound to another run or path")
    count = 0
    uncompressed = 0
    require_regular_file(path)
    with path.open("rb") as raw, gzip.GzipFile(fileobj=raw, mode="rb") as stream:
        records = iter_bounded_jsonl_records(
            cast(BinaryIO, stream),
            max_line_bytes=manifest.limits.max_evidence_bytes,
            max_wire_record_bytes=manifest.limits.max_shard_uncompressed_bytes,
        )
        for record in records:
            uncompressed += record.byte_length
            if (
                record.payload is None
                or uncompressed > manifest.limits.max_shard_uncompressed_bytes
            ):
                _reader_error("decompressed shard exceeded its bounded contract")
            evidence = _parse_evidence(record.payload)
            if evidence.source_key != receipt.source_key:
                _reader_error("evidence is bound to another shard source")
            count += 1
            yield evidence
    if count != receipt.evidence_count or uncompressed != receipt.uncompressed_bytes:
        _reader_error("decompressed shard totals do not match their receipt")
    return count


def _read_receipt(path: Path) -> FullCorpusShardReceipt:
    try:
        require_regular_file(path)
        with path.open("rb") as stream:
            raw = stream.read(_CONTROL_BYTES + 1)
        if len(raw) > _CONTROL_BYTES:
            raise ValueError
        return FullCorpusShardReceipt.model_validate_json(raw)
    except (OSError, ValidationError, ValueError) as exc:
        raise DataValidationError(
            "persona_pack_shard_receipt_invalid",
            "A persona pack shard receipt is invalid.",
        ) from exc


def _parse_evidence(raw: bytes) -> FullCorpusEvidence:
    try:
        return FullCorpusEvidence.model_validate_json(raw)
    except ValidationError as exc:
        raise DataValidationError(
            "persona_pack_evidence_invalid", "A persona evidence record is invalid."
        ) from exc


def _reader_error(reason: str) -> NoReturn:
    raise DataValidationError(
        "persona_pack_reader_invalid",
        "The bounded persona pack reader failed closed.",
        details={"reason": reason},
    )
