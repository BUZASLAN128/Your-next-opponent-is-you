from __future__ import annotations

import pytest
from pydantic import ValidationError

from ynoy.authorization import (
    build_authorization_query,
    build_trusted_authorization_tuple,
    select_authorization,
)
from ynoy.models import Mode, OutputEnvelope
from ynoy.models.formal_decision import JudgmentBasis
from ynoy.models.formal_runtime import AuthorizationQuery


def _query():
    return build_authorization_query(
        actor_id="local-os-user",
        subject_id="self",
        capability="review.append",
        scope_id="review:self:synthetic",
        confirmation_id="confirmation/1",
        audit_context_id="audit/1",
        kill_switch_id="kill/1",
    )


def test_persona_fit_never_changes_authorization() -> None:
    query = _query()
    trusted = build_trusted_authorization_tuple(query, tuple_id="grant/1")
    decisions = tuple(
        select_authorization(query, (trusted,)) for _persona_fit in ("known", "partial", "unknown")
    )

    assert decisions[0].allowed
    assert decisions[0] == decisions[1] == decisions[2]


def test_persona_state_cannot_taint_authorization_projection() -> None:
    query = _query()
    payload = query.model_dump(mode="python")
    with pytest.raises(ValidationError):
        AuthorizationQuery.model_validate({**payload, "personal_fit": "known"})
    with pytest.raises(ValidationError):
        AuthorizationQuery.model_validate({**payload, "scope_id": "persona-derived-scope"})
    trusted = build_trusted_authorization_tuple(query, tuple_id="grant/1")
    decision = select_authorization(query, (trusted,))

    assert decision.model_dump() == {
        "allowed": True,
        "reason": "trusted_unique_match",
        "tuple_id": "grant/1",
        "capability": "review.append",
        "scope_id": "review:self:synthetic",
    }


def test_persona_state_cannot_select_authorization_tuple() -> None:
    query = _query()
    candidates = (
        build_trusted_authorization_tuple(query, tuple_id="grant/1"),
        build_trusted_authorization_tuple(query, tuple_id="grant/2"),
    )
    decisions = tuple(
        select_authorization(query, candidates) for _model_choice in ("grant/1", "grant/2")
    )

    assert decisions[0] == decisions[1]
    assert not decisions[0].allowed
    assert decisions[0].reason == "trusted_match_ambiguous"


def test_v1_never_sends_executes_promotes_or_claims_action() -> None:
    outputs = tuple(
        OutputEnvelope(mode=mode, answer="Deterministic advisory.", judgment_basis=basis)
        for mode, basis in (
            (Mode.MIRROR, JudgmentBasis.EXPLICIT_POLICY),
            (Mode.MIRROR, JudgmentBasis.INFERRED_PERSONA),
            (Mode.ADVISOR, JudgmentBasis.GENERIC_ADVISOR),
            (Mode.MIRROR, JudgmentBasis.ABSTENTION),
        )
    )
    for output in outputs:
        assert output.proposed_action is None and output.action_status == "not_performed"
        assert not output.send_enabled and not output.execute_enabled
        assert not output.promotion_enabled and not output.action_claim_permitted
    with pytest.raises(ValidationError):
        OutputEnvelope(
            mode=Mode.MIRROR,
            answer="I executed the action.",
            judgment_basis=JudgmentBasis.ABSTENTION,
            proposed_action="execute",
        )
