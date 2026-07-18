from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from ynoy.errors import DataValidationError
from ynoy.models.full_persona import (
    FullCorpusFileReceipt,
    FullCorpusHead,
    FullCorpusManifest,
    FullCorpusShardReceipt,
)
from ynoy.util import canonical_json_bytes, canonical_sha256


def initial_head(manifest: FullCorpusManifest) -> FullCorpusHead:
    payload = {
        "run_id": manifest.run_id,
        "manifest_sha256": manifest.manifest_sha256,
        "revision": 0,
        "status": "frozen",
        "file_index": 0,
        "next_byte_offset": 0,
        "completed_lines": 0,
        "parser_state": {},
        "context": (),
        "processed_input_bytes": 0,
        "processed_record_count": 0,
        "evidence_count": 0,
        "quarantined_count": 0,
        "current_file_record_count": 0,
        "current_file_evidence_count": 0,
        "current_file_quarantined_count": 0,
        "current_file_exclusion_counts": {},
        "shard_count": 0,
        "output_bytes": 0,
        "exclusion_counts": {},
        "previous_head_sha256": None,
        "last_shard_sha256": None,
    }
    return seal_full_corpus_head(payload)


def seal_full_corpus_head(payload: dict[str, object]) -> FullCorpusHead:
    draft = cast(Any, FullCorpusHead).model_construct(**payload, head_sha256="0" * 64)
    return FullCorpusHead.model_validate(
        {
            **payload,
            "head_sha256": canonical_sha256(draft.model_dump(mode="json", exclude={"head_sha256"})),
        }
    )


def validate_next_head(previous: FullCorpusHead, head: FullCorpusHead) -> None:
    if (
        head.run_id != previous.run_id
        or head.manifest_sha256 != previous.manifest_sha256
        or head.revision != previous.revision + 1
        or head.previous_head_sha256 != previous.head_sha256
    ):
        raise DataValidationError(
            "full_persona_head_transition_invalid", "The next full-persona head is invalid."
        )


def validate_commit_payload(
    head: FullCorpusHead,
    staging: Path | None,
    shard: FullCorpusShardReceipt | None,
    files: tuple[FullCorpusFileReceipt, ...],
) -> None:
    if (staging is None) != (shard is None):
        raise DataValidationError(
            "full_persona_shard_receipt_missing", "A shard and its receipt must commit together."
        )
    if shard is not None and (shard.run_id != head.run_id or shard.revision != head.revision):
        raise DataValidationError(
            "full_persona_shard_binding_invalid", "A shard receipt is bound to another revision."
        )
    if any(item.run_id != head.run_id for item in files):
        raise DataValidationError(
            "full_persona_file_receipt_binding_invalid", "A file receipt belongs to another run."
        )


def model_bytes(value: BaseModel) -> bytes:
    return canonical_json_bytes(value.model_dump(mode="json"))


def pointer_bytes(head: FullCorpusHead) -> bytes:
    return canonical_json_bytes({"revision": head.revision, "head_sha256": head.head_sha256})


def validate_digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise DataValidationError(
            "full_persona_run_id_invalid", "Full-persona run identifiers must be opaque."
        )
