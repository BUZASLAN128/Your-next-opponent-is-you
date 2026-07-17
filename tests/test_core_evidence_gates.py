from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from support.canonical_claims import NOW, confirmed_admission

from ynoy.core import mirror_predict, select_evidence
from ynoy.models import (
    BootstrapDeclaration,
    CandidateKind,
    CanonicalClaim,
    DataClass,
    DecisionLabel,
    ScopeRef,
)
from ynoy.reasoner import DeterministicReasoner


@dataclass
class FakeMemory:
    declarations: list[BootstrapDeclaration] = field(default_factory=list)
    canonical_claims: list[CanonicalClaim] = field(default_factory=list)

    def list_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]:
        del include_inactive
        return [item for item in self.declarations if item.subject_id == subject_id]

    def list_active_canonical_claims(
        self, *, subject_id: str = "self", evaluation_time: datetime
    ) -> list[CanonicalClaim]:
        del evaluation_time
        return [item for item in self.canonical_claims if item.subject_id == subject_id]


def test_only_canonical_admission_can_support_prediction() -> None:
    _, _, admission = confirmed_admission(decision_label=DecisionLabel.REJECT)
    result = mirror_predict(
        FakeMemory(canonical_claims=[admission.claim]),
        task="Review evidence-backed rollback changes",
        scope=ScopeRef(project="synthetic-canonical"),
        reasoner=DeterministicReasoner(),
    )

    assert result.answer == f"Predicted decision: {DecisionLabel.REJECT.value}."
    assert result.personal_fit == "known"
    assert result.evidence_receipts == (str(admission.receipt.record_id),)


def test_legacy_candidate_reader_is_never_called() -> None:
    class PoisonLegacyMemory(FakeMemory):
        def list_claim_candidates(self, **_: object) -> list[object]:
            raise AssertionError("legacy claim candidates cannot feed Mirror")

    selected = select_evidence(
        PoisonLegacyMemory(), task="tenant", scope=ScopeRef(project="synthetic-canonical")
    )

    assert selected.items == ()


def test_future_canonical_claim_is_excluded_and_disclosed() -> None:
    _, _, admission = confirmed_admission(valid_from=NOW + timedelta(days=1))

    result = mirror_predict(
        FakeMemory(canonical_claims=[admission.claim]),
        task="evidence rollback",
        scope=ScopeRef(project="synthetic-canonical"),
        reasoner=DeterministicReasoner(),
    )

    assert result.evidence_receipts == ()
    assert "stale_evidence_was_excluded" in result.unknowns


def test_conflicting_active_canonical_claims_abstain() -> None:
    _, _, reject = confirmed_admission(offset=1, decision_label=DecisionLabel.REJECT)
    _, _, accept = confirmed_admission(offset=2, decision_label=DecisionLabel.ACCEPT)

    result = mirror_predict(
        FakeMemory(canonical_claims=[reject.claim, accept.claim]),
        task="evidence rollback",
        scope=ScopeRef(project="synthetic-canonical"),
        reasoner=DeterministicReasoner(),
    )

    assert result.personal_fit == "unknown"
    assert result.confidence == 0.0
    assert result.evidence_receipts == ()
    assert "conflicting_active_decisions" in result.unknowns


def test_conflicting_synthetic_bootstrap_declarations_abstain() -> None:
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
    assert result.evidence_receipts == ()
    assert "conflicting_active_decisions" in result.unknowns
