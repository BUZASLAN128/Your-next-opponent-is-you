from __future__ import annotations

from datetime import datetime

from ynoy.errors import DataValidationError
from ynoy.models.base import ScopeRef


def scope_matches(candidate: ScopeRef, requested: ScopeRef) -> bool:
    """Return whether a scoped item may apply without broadening its declared scope."""
    if candidate.person_id != requested.person_id:
        return False
    for field in ("project", "role", "audience"):
        candidate_value = getattr(candidate, field)
        if candidate_value is not None and candidate_value != getattr(requested, field):
            return False
    return candidate.risk == "unknown" or candidate.risk == requested.risk


def scope_is_active(scope: ScopeRef, evaluated_at: datetime) -> bool:
    """Return whether the evaluation time lies inside the declared validity interval."""
    timestamps = (evaluated_at, scope.valid_from, scope.valid_until)
    if any(value is not None and value.utcoffset() is None for value in timestamps):
        raise DataValidationError(
            "scope_time_invalid", "Scope validity comparisons require timezone-aware times."
        )
    if scope.valid_from is not None and evaluated_at < scope.valid_from:
        return False
    return scope.valid_until is None or evaluated_at <= scope.valid_until
