from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from ynoy.core import mirror_predict, select_evidence
from ynoy.models import (
    BootstrapDeclaration,
    CandidateKind,
    CandidateStatus,
    ClaimCandidate,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    ScopeRef,
)
from ynoy.reasoner import DeterministicReasoner


@dataclass
class FakeMemory:
    declarations: list[BootstrapDeclaration] = field(default_factory=list)
    candidates: list[ClaimCandidate] = field(default_factory=list)

    def list_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]:
        del include_inactive
        return [item for item in self.declarations if item.subject_id == subject_id]

    def list_claim_candidates(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[ClaimCandidate]:
        del include_inactive
        return [item for item in self.candidates if item.subject_id == subject_id]


def test_only_confirmed_represented_user_candidate_can_support_prediction() -> None:
    candidate = ClaimCandidate(
        claim_holder=ClaimHolder.REPRESENTED_USER,
        kind=CandidateKind.PREFERENCE,
        proposition="For tenant isolation changes decision:reject",
        confidence=0.8,
        status=CandidateStatus.CONFIRMED,
        scope=ScopeRef(project="pilot"),
        origin_cluster_ids=("synthetic-cluster",),
    )
    result = mirror_predict(
        FakeMemory(candidates=[candidate]),
        task="Review tenant isolation changes",
        scope=ScopeRef(project="pilot"),
        reasoner=DeterministicReasoner(),
    )
    assert result.answer == f"Predicted decision: {DecisionLabel.REJECT.value}."
    assert result.personal_fit == "known"
    assert result.evidence_receipts == (str(candidate.record_id),)


@pytest.mark.parametrize("holder", [ClaimHolder.ASSISTANT, ClaimHolder.THIRD_PARTY])
def test_non_user_or_proposed_candidate_is_not_mirror_evidence(holder: ClaimHolder) -> None:
    candidate = ClaimCandidate(
        claim_holder=holder,
        kind=CandidateKind.PREFERENCE,
        proposition="tenant decision:reject",
        confidence=1.0,
        status=CandidateStatus.PROPOSED,
        origin_cluster_ids=("synthetic-cluster",),
    )

    selected = select_evidence(FakeMemory(candidates=[candidate]), task="tenant", scope=ScopeRef())

    assert selected.items == ()


def test_future_candidate_and_scope_are_excluded_and_disclosed() -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    candidate = ClaimCandidate(
        claim_holder=ClaimHolder.REPRESENTED_USER,
        kind=CandidateKind.PREFERENCE,
        proposition="tenant decision:reject",
        confidence=1.0,
        status=CandidateStatus.CONFIRMED,
        valid_from=future,
        origin_cluster_ids=("synthetic-cluster",),
    )

    result = mirror_predict(
        FakeMemory(candidates=[candidate]),
        task="tenant",
        scope=ScopeRef(),
        reasoner=DeterministicReasoner(),
    )

    assert result.evidence_receipts == ()
    assert "stale_evidence_was_excluded" in result.unknowns


def test_conflicting_active_declarations_abstain_without_reasoner_call() -> None:
    memory = FakeMemory(
        declarations=[
            BootstrapDeclaration(
                kind=CandidateKind.PREFERENCE,
                statement="tenant decision:reject",
                decision_label=DecisionLabel.REJECT,
                source_name="fixture.json",
                data_class=DataClass.PUBLIC_SYNTHETIC,
                synthetic=True,
            ),
            BootstrapDeclaration(
                kind=CandidateKind.PREFERENCE,
                statement="tenant decision:accept",
                decision_label=DecisionLabel.ACCEPT,
                source_name="fixture.json",
                data_class=DataClass.PUBLIC_SYNTHETIC,
                synthetic=True,
            ),
        ]
    )

    result = mirror_predict(
        memory,
        task="tenant",
        scope=ScopeRef(),
        reasoner=DeterministicReasoner(),
    )

    assert result.personal_fit == "unknown"
    assert result.confidence == 0.0
    assert result.evidence_receipts == ()
    assert "conflicting_active_decisions" in result.unknowns
