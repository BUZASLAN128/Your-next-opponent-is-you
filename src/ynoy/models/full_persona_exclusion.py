from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.util import canonical_sha256, sha256_text

type Digest = str
type FullCorpusExclusionReason = Literal[
    "modified_after_stability_cutoff",
    "empty_at_freeze",
]


class FullCorpusExclusion(StrictModel):
    partition: Literal["sessions", "archived_sessions"]
    relative_locator: str = Field(min_length=1)
    source_key: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    observed_file_bytes: int = Field(ge=0)
    observed_modified_ns: int = Field(ge=1)
    device: int = Field(ge=0)
    inode: int = Field(ge=0)
    reason: FullCorpusExclusionReason
    exclusion_receipt: Digest = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exclusion_receipt_matches(self) -> FullCorpusExclusion:
        expected_key = sha256_text(f"codex-local:{self.partition}:{self.relative_locator}")
        if self.source_key != expected_key:
            raise ValueError("full-corpus exclusion source key does not match its locator")
        if self.reason == "empty_at_freeze" and self.observed_file_bytes != 0:
            raise ValueError("empty full-corpus exclusion must observe a zero-byte file")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"exclusion_receipt"}))
        if self.exclusion_receipt != expected:
            raise ValueError("full-corpus exclusion receipt does not match its payload")
        return self


def exclusion_order(value: FullCorpusExclusion) -> tuple[str, str]:
    return value.partition, value.relative_locator


def validate_exclusion_reasons(
    values: tuple[FullCorpusExclusion, ...], stable_before_ns: int
) -> None:
    for item in values:
        if item.reason == "modified_after_stability_cutoff":
            if item.observed_modified_ns <= stable_before_ns:
                raise ValueError("mutable exclusion does not exceed its stability cutoff")
        elif item.observed_modified_ns > stable_before_ns:
            raise ValueError("empty exclusion cannot hide a post-cutoff mutation")
