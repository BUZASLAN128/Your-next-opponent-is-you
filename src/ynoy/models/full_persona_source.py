from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.full_persona_chunks import validate_source_chunks
from ynoy.util import canonical_sha256

type Digest = str


class FullCorpusSource(StrictModel):
    partition: Literal["sessions", "archived_sessions"]
    relative_locator: str = Field(min_length=1)
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    file_bytes: int = Field(ge=1)
    modified_ns: int = Field(ge=1)
    device: int = Field(ge=0)
    inode: int = Field(ge=0)
    session_start_ns: int = Field(ge=1)
    thread_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    parent_thread_receipt: Digest | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    lineage_component_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    blob_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_size_bytes: int = Field(ge=64 * 1024, le=16 * 1024**2)
    chunk_sha256: tuple[Digest, ...] = Field(min_length=1)
    source_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def source_receipt_matches(self) -> FullCorpusSource:
        validate_source_chunks(self.file_bytes, self.chunk_size_bytes, self.chunk_sha256)
        payload = self.model_dump(mode="json", exclude={"source_receipt"})
        if self.source_receipt != canonical_sha256(payload):
            raise ValueError("full-corpus source receipt does not match its payload")
        return self
