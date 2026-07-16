from __future__ import annotations


class YnoyError(Exception):
    """A safe, user-facing failure with a stable error code."""

    def __init__(self, code: str, message: str, *, details: dict[str, object] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class PolicyViolation(YnoyError):
    """A fail-closed policy decision."""


class DataValidationError(YnoyError):
    """Input cannot be trusted or normalized."""


class StorageError(YnoyError):
    """Persistence boundary failed without exposing credentials."""


class AdapterError(YnoyError):
    """A model/source adapter failed or was unavailable."""
