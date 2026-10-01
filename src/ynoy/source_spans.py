from __future__ import annotations

from collections.abc import Iterable

from ynoy.errors import DataValidationError


def validate_exact_source_spans(response: str, spans: Iterable[tuple[int, int, str]]) -> None:
    """Use the same exact evidence gate for builders and serialized model admission."""
    for start, end, text in spans:
        if start < 0 or end <= start or end > len(response):
            raise DataValidationError(
                "atomic_claim_span_invalid", "Atomic claim source span is outside the response."
            )
        if response[start:end] != text:
            raise DataValidationError(
                "atomic_claim_span_mismatch", "Atomic claim source span does not match evidence."
            )
