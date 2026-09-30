"""Deterministic, source-preserving structural indexes for prepared documents."""

from .contracts import DocumentRef, NodeRead, PageRead, PreparedDocument
from .storage import StructuralIndex

__all__ = [
    "DocumentRef",
    "NodeRead",
    "PageRead",
    "PreparedDocument",
    "StructuralIndex",
]
