from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import CandidateStatus, CanonicalClaim, ScopeRef
from ynoy.models.formal_decision import (
    AdmittedDecisionClaim,
    CanonicalClaimIdentity,
    DecisionGroupKey,
    SupersessionBinding,
    canonical_identity_digest,
)
from ynoy.scope import scope_applies, scope_is_active
from ynoy.util import canonical_sha256


def build_claim_identity(
    claim: CanonicalClaim,
    *,
    reviewed_decision_key: str,
    decision_key_receipt_sha256: str,
) -> CanonicalClaimIdentity:
    """Bind an immutable claim tuple to one user-reviewed decision key."""
    draft = CanonicalClaimIdentity.model_construct(
        claim_id=claim.record_id,
        subject_id=claim.subject_id,
        target_layer=claim.target_layer,
        reviewed_decision_key=reviewed_decision_key,
        claim_tuple_sha256=claim.claim_sha256,
        decision_key_receipt_sha256=decision_key_receipt_sha256,
        identity_sha256="0" * 64,
    )
    return CanonicalClaimIdentity.model_validate(
        {**draft.model_dump(mode="python"), "identity_sha256": canonical_identity_digest(draft)}
    )


def admit_decision_claim(
    claim: CanonicalClaim, identity: CanonicalClaimIdentity
) -> AdmittedDecisionClaim:
    """Admit only a claim whose reviewed identity binds every immutable field."""
    try:
        return AdmittedDecisionClaim(claim=claim, identity=identity)
    except ValidationError as exc:
        raise DataValidationError(
            "canonical_decision_identity_invalid",
            "Canonical decision identity does not bind the claim.",
        ) from exc


def build_supersession_binding(
    successor: AdmittedDecisionClaim,
    predecessor: AdmittedDecisionClaim,
    *,
    review_sha256: str,
    expected_head: int,
) -> SupersessionBinding:
    draft = SupersessionBinding.model_construct(
        successor_claim_id=successor.claim.record_id,
        predecessor_claim_id=predecessor.claim.record_id,
        successor_tuple_sha256=successor.claim.claim_sha256,
        predecessor_tuple_sha256=predecessor.claim.claim_sha256,
        full_key=successor.identity.full_key,
        review_sha256=review_sha256,
        expected_head=expected_head,
        receipt_sha256="0" * 64,
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"receipt_sha256"}))
    return SupersessionBinding.model_validate(
        {**draft.model_dump(mode="python"), "receipt_sha256": digest}
    )


def claim_applies(
    admitted: AdmittedDecisionClaim,
    requested_scope: ScopeRef,
    evaluation_time: datetime,
) -> bool:
    claim = admitted.claim
    return (
        claim.status == CandidateStatus.CONFIRMED
        and claim.subject_id == requested_scope.person_id
        and scope_applies(claim.scope, requested_scope)
        and scope_is_active(claim.scope, evaluation_time)
    )


def valid_supersedes(
    successor: AdmittedDecisionClaim,
    predecessor: AdmittedDecisionClaim,
    binding: SupersessionBinding,
    *,
    requested_scope: ScopeRef,
    evaluation_time: datetime,
) -> bool:
    """Validate query-specific supersession without recency or similarity fallback."""
    expected = (
        successor.claim.record_id,
        predecessor.claim.record_id,
        successor.claim.claim_sha256,
        predecessor.claim.claim_sha256,
        successor.identity.full_key,
    )
    actual = (
        binding.successor_claim_id,
        binding.predecessor_claim_id,
        binding.successor_tuple_sha256,
        binding.predecessor_tuple_sha256,
        binding.full_key,
    )
    return (
        expected == actual
        and successor.claim.supersedes_claim_id == predecessor.claim.record_id
        and successor.identity.full_key == predecessor.identity.full_key
        and claim_applies(successor, requested_scope, evaluation_time)
        and claim_applies(predecessor, requested_scope, evaluation_time)
    )


def group_key(admitted: AdmittedDecisionClaim) -> DecisionGroupKey:
    return admitted.identity.full_key
