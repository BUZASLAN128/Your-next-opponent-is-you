from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

TreeNodeInput = Mapping[str, object]
TreeInput = TreeNodeInput | Sequence[TreeNodeInput]


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    """A prepared document with exact page text and a PageIndex-compatible tree."""

    name: str
    pages: Sequence[str]
    tree: TreeInput
    description: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """Stable public metadata for one immutable imported document."""

    document_id: str
    name: str
    description: str | None
    page_count: int
    content_sha256: str


@dataclass(frozen=True, slots=True)
class PageRead:
    """Exact source text for one 1-based page and its integrity reference."""

    document_id: str
    page_number: int
    source_ref: str
    content_sha256: str
    text: str


@dataclass(frozen=True, slots=True)
class NodeRead:
    """Navigation summary plus exact source pages covered by an inclusive span.

    The optional summary is navigation-only and must never be treated as evidence.
    """

    document_id: str
    node_id: str
    title: str
    start_index: int
    end_index: int
    summary: str | None
    pages: tuple[PageRead, ...]
