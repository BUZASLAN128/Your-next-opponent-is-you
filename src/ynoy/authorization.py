from __future__ import annotations

from collections.abc import Sequence

from ynoy.models.formal_runtime import (
    AuthorizationDecision,
    AuthorizationQuery,
    TrustedAuthorizationTuple,
)
from ynoy.util import canonical_sha256


def build_authorization_query(
    *,
    actor_id: str,
    subject_id: str,
    capability: str,
    scope_id: str,
    confirmation_id: str,
    audit_context_id: str,
    kill_switch_id: str,
) -> AuthorizationQuery:
    draft = AuthorizationQuery.model_construct(
        actor_id=actor_id,
        subject_id=subject_id,
        capability=capability,
        scope_id=scope_id,
        confirmation_id=confirmation_id,
        audit_context_id=audit_context_id,
        kill_switch_id=kill_switch_id,
        request_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="python")
    payload["request_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"request_sha256"})
    )
    return AuthorizationQuery.model_validate(payload)


def build_trusted_authorization_tuple(
    query: AuthorizationQuery,
    *,
    tuple_id: str,
) -> TrustedAuthorizationTuple:
    draft = TrustedAuthorizationTuple.model_construct(
        **query.model_dump(mode="python"),
        tuple_id=tuple_id,
        enabled=True,
        receipt_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="python")
    payload["receipt_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"receipt_sha256"})
    )
    return TrustedAuthorizationTuple.model_validate(payload)


def select_authorization(
    query: AuthorizationQuery,
    candidates: Sequence[TrustedAuthorizationTuple],
) -> AuthorizationDecision:
    matches = tuple(item for item in candidates if _matches(query, item))
    if not matches:
        return AuthorizationDecision(allowed=False, reason="trusted_match_missing")
    if len(matches) != 1:
        return AuthorizationDecision(allowed=False, reason="trusted_match_ambiguous")
    selected = matches[0]
    return AuthorizationDecision(
        allowed=True,
        reason="trusted_unique_match",
        tuple_id=selected.tuple_id,
        capability=selected.capability,
        scope_id=selected.scope_id,
    )


def _matches(query: AuthorizationQuery, candidate: TrustedAuthorizationTuple) -> bool:
    trusted_fields = (
        "actor_id",
        "subject_id",
        "capability",
        "scope_id",
        "confirmation_id",
        "audit_context_id",
        "kill_switch_id",
    )
    return candidate.enabled and all(
        getattr(query, field) == getattr(candidate, field) for field in trusted_fields
    )
