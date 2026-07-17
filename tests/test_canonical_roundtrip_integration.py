from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from conftest import synthetic_audit
from support.canonical_claims import NOW, confirmed_admission

from ynoy.errors import DataValidationError
from ynoy.models import CandidateStatus, CanonicalClaimAdmission, DataClass, DecisionLabel
from ynoy.storage import CanonicalClaimRepository, Database, ErasureRepository

pytestmark = pytest.mark.integration


def test_review_admit_retrieve_supersede_erase_round_trip(test_database: Database) -> None:
    seed = uuid4().int % 1_000_000 + 1_000_000
    subject_id = f"canonical-roundtrip-{uuid4()}"
    _, _, first = confirmed_admission(
        offset=seed,
        subject_id=subject_id,
        decision_label=DecisionLabel.REJECT,
    )
    repository = CanonicalClaimRepository(test_database, data_class=DataClass.PUBLIC_SYNTHETIC)

    assert repository.admit(first, synthetic_audit(artifact_id=str(first.claim.record_id)))
    assert not repository.admit(first, synthetic_audit(artifact_id=str(first.claim.record_id)))
    assert repository.provenance(first.claim.record_id) == first
    active = repository.list_active_canonical_claims(
        subject_id=subject_id, evaluation_time=NOW + timedelta(days=1)
    )
    assert active == [first.claim]

    _, _, second = confirmed_admission(
        offset=seed + 1,
        subject_id=subject_id,
        decision_label=DecisionLabel.ACCEPT,
        supersedes_claim_id=first.claim.record_id,
    )
    assert repository.admit(second, synthetic_audit(artifact_id=str(second.claim.record_id)))
    current = repository.list_active_canonical_claims(
        subject_id=subject_id, evaluation_time=NOW + timedelta(days=1)
    )
    assert current == [second.claim]
    history = repository.inspect_canonical_claims(subject_id=subject_id, include_inactive=True)
    assert [item.status for item in history] == [
        CandidateStatus.SUPERSEDED,
        CandidateStatus.CONFIRMED,
    ]
    assert history[0].superseded_by == second.claim.record_id

    _erase_and_assert(test_database, repository, subject_id, second)


def _erase_and_assert(
    database: Database,
    repository: CanonicalClaimRepository,
    subject_id: str,
    admission: CanonicalClaimAdmission,
) -> None:
    erasure = ErasureRepository(database)
    source_id = str(admission.source_links[0].source_receipt_id)

    plan = erasure.plan(source_id=source_id)
    assert plan["target_counts"]["canonical_claims"] == 1
    assert plan["target_counts"]["claim_source_links"] == 1
    assert plan["target_counts"]["claim_admission_receipts"] == 1
    erasure.confirm_database(
        plan_id=UUID(str(plan["plan_id"])),
        plan_sha256=str(plan["plan_sha256"]),
    )
    assert (
        repository.list_active_canonical_claims(
            subject_id=subject_id, evaluation_time=NOW + timedelta(days=1)
        )
        == []
    )
    with pytest.raises(DataValidationError) as missing:
        repository.provenance(admission.claim.record_id)
    assert missing.value.code == "canonical_claim_not_found"
    erasure.finalize(
        plan_id=UUID(str(plan["plan_id"])),
        plan_sha256=str(plan["plan_sha256"]),
    )


@pytest.mark.parametrize("window", ["future", "expired"])
def test_time_inactive_canonical_claim_is_not_retrieved(
    test_database: Database, window: str
) -> None:
    seed = uuid4().int % 1_000_000 + 3_000_000
    subject_id = f"canonical-time-{window}-{uuid4()}"
    bounds = (
        {"valid_from": NOW + timedelta(days=2)}
        if window == "future"
        else {"valid_until": NOW + timedelta(hours=1)}
    )
    admission = confirmed_admission(
        offset=seed,
        subject_id=subject_id,
        **bounds,
    )[2]
    repository = CanonicalClaimRepository(test_database, data_class=DataClass.PUBLIC_SYNTHETIC)
    repository.admit(admission, synthetic_audit(artifact_id=str(admission.claim.record_id)))

    evaluation_time = NOW if window == "future" else NOW + timedelta(days=1)
    assert (
        repository.list_active_canonical_claims(
            subject_id=subject_id, evaluation_time=evaluation_time
        )
        == []
    )


def test_broken_source_link_fails_closed_from_retrieval(test_database: Database) -> None:
    seed = uuid4().int % 1_000_000 + 4_000_000
    subject_id = f"canonical-broken-source-{uuid4()}"
    admission = confirmed_admission(offset=seed, subject_id=subject_id)[2]
    repository = CanonicalClaimRepository(test_database, data_class=DataClass.PUBLIC_SYNTHETIC)
    repository.admit(admission, synthetic_audit(artifact_id=str(admission.claim.record_id)))
    with test_database.connect() as connection:
        connection.execute(
            "DELETE FROM ynoy.claim_source_links WHERE claim_id = %s",
            (admission.claim.record_id,),
        )

    assert (
        repository.list_active_canonical_claims(
            subject_id=subject_id, evaluation_time=NOW + timedelta(days=1)
        )
        == []
    )
    with pytest.raises(DataValidationError) as missing:
        repository.provenance(admission.claim.record_id)
    assert missing.value.code == "canonical_claim_not_found"
