from __future__ import annotations

import gzip
import os
from typing import Any, BinaryIO, cast

from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import (
    FullCorpusEvidence,
    FullCorpusLimits,
    FullCorpusShardReceipt,
    FullCorpusSource,
)
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_file


class ShardBuffer:
    """Write one source-isolated gzip shard without retaining evidence in memory."""

    def __init__(
        self,
        store: FullPersonaStore,
        run_id: str,
        source: FullCorpusSource,
        limits: FullCorpusLimits,
    ) -> None:
        self.path = store.new_staging_path(run_id)
        self.run_id = run_id
        self.source = source
        self.limits = limits
        self._raw: BinaryIO = self.path.open("xb")
        self._gzip = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0)
        self.record_count = 0
        self.uncompressed_bytes = 0
        self.start_offset = 0
        self.end_offset = 0
        self.start_line = 0
        self.end_line = 0
        self._closed = False

    def encoded(self, evidence: FullCorpusEvidence) -> bytes:
        return canonical_json_bytes(evidence.model_dump(mode="json")) + b"\n"

    def can_accept(self, encoded: bytes) -> bool:
        if self.record_count == 0:
            return len(encoded) <= self.limits.max_shard_uncompressed_bytes
        return (
            self.record_count < self.limits.max_shard_records
            and self.uncompressed_bytes + len(encoded) <= self.limits.max_shard_uncompressed_bytes
        )

    def write(self, evidence: FullCorpusEvidence, encoded: bytes) -> None:
        if not self.can_accept(encoded):
            raise ValueError("full-persona shard is full")
        if self.record_count == 0:
            self.start_offset = evidence.byte_start
            self.start_line = evidence.line_number
        self._gzip.write(encoded)
        self.record_count += 1
        self.uncompressed_bytes += len(encoded)
        self.end_offset = evidence.byte_start + evidence.byte_length
        self.end_line = evidence.line_number

    def finish(self, revision: int) -> FullCorpusShardReceipt | None:
        self._close()
        if self.record_count == 0:
            self.path.unlink(missing_ok=True)
            return None
        compressed_bytes = self.path.stat().st_size
        payload = {
            "run_id": self.run_id,
            "revision": revision,
            "relative_path": f"shards/{revision:08d}.jsonl.gz",
            "source_key": self.source.source_key,
            "start_byte_offset": self.start_offset,
            "end_byte_offset": self.end_offset,
            "start_line_number": self.start_line,
            "end_line_number": self.end_line,
            "evidence_count": self.record_count,
            "uncompressed_bytes": self.uncompressed_bytes,
            "compressed_bytes": compressed_bytes,
            "content_sha256": sha256_file(self.path),
        }
        draft = cast(Any, FullCorpusShardReceipt).model_construct(
            **payload, receipt_sha256="0" * 64
        )
        return FullCorpusShardReceipt.model_validate(
            {
                **payload,
                "receipt_sha256": canonical_sha256(
                    draft.model_dump(mode="json", exclude={"receipt_sha256"})
                ),
            }
        )

    def abort(self) -> None:
        self._close()
        self.path.unlink(missing_ok=True)

    def _close(self) -> None:
        if self._closed:
            return
        try:
            self._gzip.close()
            self._raw.flush()
            os.fsync(self._raw.fileno())
        finally:
            self._raw.close()
            self._closed = True
