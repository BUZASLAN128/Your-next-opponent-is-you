from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from ynoy.constants import DEFAULT_EMBEDDING_DIMENSIONS, DEFAULT_EMBEDDING_MODEL
from ynoy.errors import AdapterError, DataValidationError
from ynoy.local_http import post_json
from ynoy.models import DataClass
from ynoy.policy import is_loopback_url

MAX_EMBEDDING_TEXTS = 64
MAX_EMBEDDING_INPUT_BYTES = 1024 * 1024
MAX_EMBEDDING_RESPONSE_BYTES = 8 * 1024 * 1024


class EmbeddingAdapter(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    @property
    def is_local(self) -> bool: ...

    def embed(
        self, texts: tuple[str, ...], *, data_class: DataClass
    ) -> tuple[tuple[float, ...], ...]: ...


@dataclass(frozen=True, slots=True)
class LocalOpenAIEmbeddingAdapter:
    endpoint: str
    model: str = DEFAULT_EMBEDDING_MODEL
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    timeout_seconds: float = 120.0
    is_local: bool = False

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "local_embedding_not_loopback",
                "The embedding endpoint must use HTTP on a loopback address.",
            )

    def embed(
        self, texts: tuple[str, ...], *, data_class: DataClass
    ) -> tuple[tuple[float, ...], ...]:
        if not self.is_local and data_class != DataClass.PUBLIC_SYNTHETIC:
            raise DataValidationError(
                "external_embedding_persona_blocked",
                "Unattested embedding adapters are limited to public or synthetic D0 input.",
            )
        if not texts:
            return ()
        if (
            len(texts) > MAX_EMBEDDING_TEXTS
            or sum(len(value.encode("utf-8")) for value in texts) > MAX_EMBEDDING_INPUT_BYTES
        ):
            raise DataValidationError(
                "embedding_input_too_large",
                "Embedding input exceeds the 64-item or 1 MiB local limit.",
            )
        result = post_json(
            self.endpoint,
            {"model": self.model, "input": texts},
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=MAX_EMBEDDING_RESPONSE_BYTES,
            error_prefix="local_embedding",
        )
        return self._validate_response(result, len(texts))

    def _validate_response(
        self, result: object, expected_count: int
    ) -> tuple[tuple[float, ...], ...]:
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise AdapterError(
                "local_embedding_schema_invalid", "Embedding response has an invalid schema."
            )
        vectors = tuple(_vector(item, self.dimensions) for item in result["data"])
        if len(vectors) != expected_count:
            raise AdapterError(
                "local_embedding_count_mismatch", "Embedding response count is inconsistent."
            )
        return vectors


def _vector(item: object, dimensions: int) -> tuple[float, ...]:
    if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
        raise AdapterError(
            "local_embedding_schema_invalid", "Embedding item has an invalid schema."
        )
    values = tuple(float(value) for value in item["embedding"])
    if len(values) != dimensions or not all(math.isfinite(value) for value in values):
        raise AdapterError(
            "local_embedding_dimensions_invalid",
            "Embedding vector has invalid dimensions or non-finite values.",
        )
    return values
