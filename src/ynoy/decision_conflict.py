from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from uuid import UUID

from ynoy.decision_identity import claim_applies, valid_supersedes
from ynoy.models import ScopeRef
from ynoy.models.formal_decision import (
    AdmittedDecisionClaim,
    ConflictAssessment,
    ConflictRelation,
    DecisionGroupKey,
    RequiredDecisionGroups,
    SupersessionBinding,
)
from ynoy.util import canonical_sha256


@dataclass(frozen=True, slots=True)
class DecisionResolution:
    active_claims: tuple[AdmittedDecisionClaim, ...]
    unsafe_keys: tuple[DecisionGroupKey, ...]
    reasons: tuple[str, ...]

    @property
    def safe(self) -> bool:
        return not self.reasons


def build_required_groups(
    groups: tuple[DecisionGroupKey, ...], *, version: str
) -> RequiredDecisionGroups:
    ordered = tuple(sorted(groups, key=_key_sort))
    draft = RequiredDecisionGroups.model_construct(
        version=version,
        groups=ordered,
        manifest_sha256="0" * 64,
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"manifest_sha256"}))
    return RequiredDecisionGroups.model_validate(
        {**draft.model_dump(mode="python"), "manifest_sha256": digest}
    )


def resolve_decision_groups(
    claims: tuple[AdmittedDecisionClaim, ...],
    assessments: tuple[ConflictAssessment, ...],
    supersession_bindings: tuple[SupersessionBinding, ...],
    manifest: RequiredDecisionGroups,
    *,
    expected_groups: tuple[DecisionGroupKey, ...],
    requested_scope: ScopeRef,
    evaluation_time: datetime,
) -> DecisionResolution:
    """Resolve query-valid groups while keeping missing relations unsafe and visible."""
    expected = tuple(sorted(expected_groups, key=_key_sort))
    if manifest.groups != expected:
        return DecisionResolution((), expected, ("required_decision_group_manifest_mismatch",))
    applicable = tuple(
        item for item in claims if claim_applies(item, requested_scope, evaluation_time)
    )
    active, supersession_unsafe = _apply_supersession(
        applicable,
        supersession_bindings,
        requested_scope,
        evaluation_time,
    )
    groups = _group_claims(active)
    unsafe = set(supersession_unsafe)
    reasons: set[str] = set()
    if supersession_unsafe:
        reasons.add("invalid_or_unresolved_supersession")
    assessment_index = {_assessment_key(item): item for item in assessments}
    for key, members in groups.items():
        for left, right in combinations(members, 2):
            assessment = assessment_index.get(_pair_key(key, left, right))
            relation = ConflictRelation.UNKNOWN if assessment is None else assessment.relation
            if relation in {ConflictRelation.INCOMPATIBLE, ConflictRelation.UNKNOWN}:
                unsafe.add(key)
                reasons.add(f"decision_group_{relation.value}")
    missing = set(expected) - set(groups)
    if missing:
        unsafe.update(missing)
        reasons.add("required_decision_group_missing")
    return DecisionResolution(
        tuple(sorted(active, key=lambda item: str(item.claim.record_id))),
        tuple(sorted(unsafe, key=_key_sort)),
        tuple(sorted(reasons)),
    )


def _apply_supersession(
    claims: tuple[AdmittedDecisionClaim, ...],
    bindings: tuple[SupersessionBinding, ...],
    requested_scope: ScopeRef,
    evaluation_time: datetime,
) -> tuple[tuple[AdmittedDecisionClaim, ...], set[DecisionGroupKey]]:
    by_id = {item.claim.record_id: item for item in claims}
    binding_index = {
        (item.successor_claim_id, item.predecessor_claim_id): item for item in bindings
    }
    suppressed: set[UUID] = set()
    unsafe: set[DecisionGroupKey] = set()
    edges: dict[UUID, UUID] = {}
    for successor in claims:
        predecessor_id = successor.claim.supersedes_claim_id
        if predecessor_id is None:
            continue
        predecessor = by_id.get(predecessor_id)
        binding = binding_index.get((successor.claim.record_id, predecessor_id))
        if (
            predecessor is None
            or binding is None
            or not valid_supersedes(
                successor,
                predecessor,
                binding,
                requested_scope=requested_scope,
                evaluation_time=evaluation_time,
            )
        ):
            unsafe.add(successor.identity.full_key)
            continue
        edges[successor.claim.record_id] = predecessor_id
        suppressed.add(predecessor_id)
    for node in edges:
        if _has_cycle(node, edges):
            unsafe.add(by_id[node].identity.full_key)
    if unsafe:
        suppressed = {
            claim_id for claim_id in suppressed if by_id[claim_id].identity.full_key not in unsafe
        }
    return tuple(item for item in claims if item.claim.record_id not in suppressed), unsafe


def _has_cycle(start: UUID, edges: dict[UUID, UUID]) -> bool:
    seen: set[UUID] = set()
    current: UUID | None = start
    while current in edges:
        if current in seen:
            return True
        seen.add(current)
        current = edges[current]
    return False


def _group_claims(
    claims: tuple[AdmittedDecisionClaim, ...],
) -> dict[DecisionGroupKey, tuple[AdmittedDecisionClaim, ...]]:
    values: dict[DecisionGroupKey, list[AdmittedDecisionClaim]] = {}
    for claim in claims:
        values.setdefault(claim.identity.full_key, []).append(claim)
    return {key: tuple(items) for key, items in values.items()}


def _assessment_key(assessment: ConflictAssessment) -> tuple[DecisionGroupKey, str, str]:
    return (assessment.full_key, str(assessment.left_claim_id), str(assessment.right_claim_id))


def _pair_key(
    key: DecisionGroupKey,
    left: AdmittedDecisionClaim,
    right: AdmittedDecisionClaim,
) -> tuple[DecisionGroupKey, str, str]:
    claim_ids = sorted((str(left.claim.record_id), str(right.claim.record_id)))
    return key, claim_ids[0], claim_ids[1]


def _key_sort(key: DecisionGroupKey) -> tuple[str, str, str]:
    return key.subject_id, key.target_layer.value, key.reviewed_decision_key
