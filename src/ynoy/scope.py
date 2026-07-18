from __future__ import annotations

from datetime import datetime

from ynoy.errors import DataValidationError
from ynoy.models.base import ScopeRef


def scope_applies(candidate: ScopeRef, requested: ScopeRef) -> bool:
    """Return whether a stored scope applies to the concrete query environment."""
    if candidate.person_id != requested.person_id:
        return False
    for field in ("project", "role", "audience"):
        candidate_value = getattr(candidate, field)
        if candidate_value is not None and candidate_value != getattr(requested, field):
            return False
    return candidate.risk == "any" or candidate.risk == requested.risk


def scope_matches(candidate: ScopeRef, requested: ScopeRef) -> bool:
    """Compatibility alias for the V1.7 query-membership contract."""
    return scope_applies(candidate, requested)


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
