from __future__ import annotations

from enum import StrEnum


class DataPlane(StrEnum):
    """Immutable storage identity for private or public synthetic data."""

    PRIVATE = "private"
    PUBLIC_SYNTHETIC = "public_synthetic"

    @property
    def application_id(self) -> int:
        if self is DataPlane.PRIVATE:
            return 0x594E4D32
        return 0x594E5332


__all__ = ["DataPlane"]
