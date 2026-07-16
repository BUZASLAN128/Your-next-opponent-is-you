from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from conftest import synthetic_audit

from ynoy.bootstrap import load_bootstrap
from ynoy.models import CandidateKind, ClaimCandidate, ClaimHolder, DataClass, ScopeRef
from ynoy.storage import Database, ErasureRepository, MemoryMutationRepository

pytestmark = pytest.mark.integration


def _confirm_and_finalize(database: Database, plan: dict[str, object]) -> UUID:
    repository = ErasureRepository(database)
    plan_id = UUID(str(plan["plan_id"]))
    digest = str(plan["plan_sha256"])
    result = repository.confirm_database(plan_id=plan_id, plan_sha256=digest)
    assert result["database_deleted"] is True
    assert _audit_count(database, plan_id, "local_database_deleted_pending_artifact_cleanup") == 1
    assert _audit_count(database, plan_id, "local_dependency_cascade_deleted") == 0
    repository.finalize(plan_id=plan_id, plan_sha256=digest)
    assert _audit_count(database, plan_id, "local_dependency_cascade_deleted") == 1
    return plan_id


def _audit_count(database: Database, plan_id: UUID, reason_code: str) -> int:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT count(*) AS count FROM ynoy.audit_receipts
            WHERE reason_code = %s
              AND opaque_input_ids @> ARRAY[%s]
            """,
            (reason_code, str(plan_id)),
        ).fetchone()
    assert row is not None
    return int(row["count"])


def test_source_record_erasure_removes_all_bootstrap_declarations_and_source(
    test_database: Database, tmp_path: Path
) -> None:
    source = tmp_path / "multi-source.json"
    marker = str(uuid4())
    source.write_text(
        json.dumps(
            [
                {"statement": f"first {marker}", "synthetic": True},
                {"statement": f"second {marker}", "synthetic": True},
            ]
        ),
        encoding="utf-8",
    )
    declarations = load_bootstrap(source, synthetic=True)
    source_id = declarations[0].source_record_id
    assert {item.source_record_id for item in declarations} == {source_id}
    MemoryMutationRepository(test_database).add_bootstrap_declarations(
        declarations, synthetic_audit()
    )
    plan = ErasureRepository(test_database).plan(source_id=str(source_id))
    assert plan["target_counts"]["bootstrap_sources"] == 1
    assert plan["target_counts"]["bootstrap_declarations"] == 2
    plan_id = _confirm_and_finalize(test_database, plan)
    with test_database.connect() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM ynoy.bootstrap_sources
               WHERE record_id = %s) AS sources,
              (SELECT count(*) FROM ynoy.bootstrap_declarations
               WHERE source_record_id = %s) AS declarations
            """,
            (source_id, source_id),
        ).fetchone()
    assert row is not None and row["sources"] == 0 and row["declarations"] == 0
    assert _audit_count(test_database, plan_id, "local_dependency_cascade_deleted") == 1


def test_direct_derived_record_erasure_removes_claim_and_leaves_tombstone(
    test_database: Database,
) -> None:
    subject_id = f"erasure-claim-{uuid4()}"
    candidate = ClaimCandidate(
        subject_id=subject_id,
        claim_holder=ClaimHolder.REPRESENTED_USER,
        kind=CandidateKind.PREFERENCE,
        proposition=f"derived synthetic candidate {uuid4()}",
        scope=ScopeRef(person_id=subject_id),
        confidence=0.7,
        origin_cluster_ids=(f"cluster-{uuid4()}",),
    )
    audit = synthetic_audit().model_copy(update={"data_classes": (DataClass.DERIVED_IDENTITY,)})
    MemoryMutationRepository(test_database).add_claim_candidates([candidate], audit)
    plan = ErasureRepository(test_database).plan(source_id=str(candidate.record_id))
    assert plan["target_counts"]["claim_candidates"] == 1
    plan_id = _confirm_and_finalize(test_database, plan)
    with test_database.connect() as connection:
        row = connection.execute(
            "SELECT count(*) AS count FROM ynoy.claim_candidates WHERE record_id = %s",
            (candidate.record_id,),
        ).fetchone()
    assert row is not None and row["count"] == 0
    assert _audit_count(test_database, plan_id, "local_dependency_cascade_deleted") == 1
