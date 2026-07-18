from __future__ import annotations

from datetime import timedelta

import pytest
from support.canonical_claims import NOW
from support.formal_decisions import admitted_claim

from ynoy.decision_conflict import build_required_groups, resolve_decision_groups
from ynoy.decision_identity import admit_decision_claim, build_supersession_binding
from ynoy.errors import DataValidationError
from ynoy.models import DecisionLabel, ScopeRef
from ynoy.models.formal_decision import ConflictAssessment, ConflictRelation
from ynoy.scope import scope_applies


def _resolve(claims, assessments=(), bindings=(), expected=None, manifest=None):
    groups = expected or tuple(sorted({item.identity.full_key for item in claims}, key=str))
    frozen = manifest or build_required_groups(groups, version="fixture/1")
    return resolve_decision_groups(
        tuple(claims),
        tuple(assessments),
        tuple(bindings),
        frozen,
        expected_groups=groups,
        requested_scope=ScopeRef(project="synthetic-canonical"),
        evaluation_time=NOW,
    )


def _assessment(left, right, relation: ConflictRelation) -> ConflictAssessment:
    ordered = sorted((left.claim.record_id, right.claim.record_id), key=str)
    return ConflictAssessment(
        left_claim_id=ordered[0],
        right_claim_id=ordered[1],
        full_key=left.identity.full_key,
        relation=relation,
        evidence_sha256="a" * 64,
        reason="Synthetic deterministic relation.",
    )


def test_general_scope_applies_to_specific_query() -> None:
    general = ScopeRef(project=None, role=None, risk="any")
    specific = ScopeRef(project="alpha", role="reviewer", risk="high")

    assert scope_applies(general, specific)
    assert not scope_applies(specific, general)
    assert not scope_applies(specific, ScopeRef(project="beta", role="reviewer", risk="high"))


def test_risk_unknown_is_not_high_and_any_is_wildcard() -> None:
    high = ScopeRef(risk="high")

    assert not scope_applies(ScopeRef(risk="unknown"), high)
    assert scope_applies(ScopeRef(risk="any"), high)
    assert scope_applies(ScopeRef(risk="unknown"), ScopeRef(risk="unknown"))


def test_canonical_claim_requires_subject_and_reviewed_decision_key() -> None:
    admitted = admitted_claim()
    wrong_subject = admitted.identity.model_copy(update={"subject_id": "other"})
    missing_key = admitted.identity.model_copy(update={"reviewed_decision_key": ""})

    for invalid in (wrong_subject, missing_key):
        with pytest.raises(DataValidationError) as blocked:
            admit_decision_claim(admitted.claim, invalid)
        assert blocked.value.code == "canonical_decision_identity_invalid"


def test_unknown_same_key_relation_abstains() -> None:
    left = admitted_claim(offset=1)
    right = admitted_claim(offset=2, decision_label=DecisionLabel.ACCEPT)

    resolution = _resolve((left, right))

    assert not resolution.safe
    assert resolution.reasons == ("decision_group_unknown",)


def test_conflict_requires_two_distinct_active_claims() -> None:
    claim = admitted_claim()

    resolution = _resolve((claim,))

    assert resolution.safe and not resolution.unsafe_keys
    with pytest.raises(ValueError, match="distinct"):
        _assessment(claim, claim, ConflictRelation.INCOMPATIBLE)


def test_different_keys_do_not_create_false_conflict() -> None:
    left = admitted_claim(offset=1, decision_key="review-api")
    right = admitted_claim(offset=2, decision_key="deploy-api", decision_label=DecisionLabel.ACCEPT)

    resolution = _resolve((left, right))

    assert resolution.safe


def test_required_decision_group_omission_abstains() -> None:
    left = admitted_claim(offset=1, decision_key="review-api")
    right = admitted_claim(offset=2, decision_key="deploy-api")
    expected = (left.identity.full_key, right.identity.full_key)
    incomplete = build_required_groups((left.identity.full_key,), version="fixture/1")

    resolution = _resolve((left, right), expected=expected, manifest=incomplete)

    assert resolution.reasons == ("required_decision_group_manifest_mismatch",)


def test_supersession_requires_active_applicable_same_subject_key() -> None:
    predecessor = admitted_claim(offset=1)
    successor = admitted_claim(offset=2, supersedes_claim_id=predecessor.claim.record_id)
    binding = build_supersession_binding(
        successor,
        predecessor,
        review_sha256="b" * 64,
        expected_head=1,
    )

    resolution = _resolve((predecessor, successor), bindings=(binding,))

    assert resolution.safe
    assert tuple(item.claim.record_id for item in resolution.active_claims) == (
        successor.claim.record_id,
    )


@pytest.mark.parametrize("invalid_kind", ["wrong_key", "expired", "missing_binding"])
def test_invalid_supersession_cannot_hide_active_claim(invalid_kind: str) -> None:
    predecessor = admitted_claim(offset=10)
    successor = admitted_claim(
        offset=11,
        decision_key="other" if invalid_kind == "wrong_key" else "synthetic-change-decision",
        valid_until=NOW - timedelta(seconds=1) if invalid_kind == "expired" else None,
        supersedes_claim_id=predecessor.claim.record_id,
    )
    binding = build_supersession_binding(
        successor,
        predecessor,
        review_sha256="c" * 64,
        expected_head=1,
    )
    bindings = () if invalid_kind == "missing_binding" else (binding,)

    resolution = _resolve((predecessor, successor), bindings=bindings)

    assert predecessor.claim.record_id in {
        item.claim.record_id for item in resolution.active_claims
    }
