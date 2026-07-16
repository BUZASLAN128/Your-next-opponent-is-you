from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from conftest import synthetic_audit
from psycopg.types.json import Jsonb

from ynoy.core import select_evidence
from ynoy.errors import PolicyViolation
from ynoy.models import (
    AuditReceipt,
    BootstrapDeclaration,
    CandidateKind,
    ClaimCandidate,
    ClaimHolder,
    DataClass,
    ScopeRef,
)
from ynoy.storage import (
    Database,
    MemoryInspectionRepository,
    MemoryMutationRepository,
    MemoryRepository,
)

pytestmark = pytest.mark.integration


def _audit(data_class: DataClass) -> AuditReceipt:
    return synthetic_audit().model_copy(update={"data_classes": (data_class,)})


def _declaration(subject_id: str, *, synthetic: bool) -> BootstrapDeclaration:
    return BootstrapDeclaration(
        subject_id=subject_id,
        kind=CandidateKind.PREFERENCE,
        statement="Prefer reversible evidence-backed changes.",
        scope=ScopeRef(person_id=subject_id),
        source_name="synthetic.json" if synthetic else "legacy-private.json",
        data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY),
        synthetic=synthetic,
    )


def _candidate(subject_id: str) -> ClaimCandidate:
    return ClaimCandidate(
        subject_id=subject_id,
        claim_holder=ClaimHolder.REPRESENTED_USER,
        kind=CandidateKind.PREFERENCE,
        proposition="Prefer reversible evidence-backed changes.",
        scope=ScopeRef(person_id=subject_id),
        confidence=0.9,
        origin_cluster_ids=(f"cluster-{subject_id}",),
    )


def _seed_bootstrap_directly(database: Database, declaration: BootstrapDeclaration) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO ynoy.bootstrap_declarations (
                record_id, subject_id, kind, statement, scope, decision_label,
                source_name, data_class, synthetic, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                declaration.record_id,
                declaration.subject_id,
                declaration.kind.value,
                declaration.statement,
                Jsonb(declaration.scope.model_dump(mode="json")),
                None,
                declaration.source_name,
                declaration.data_class.value,
                declaration.synthetic,
                declaration.status.value,
                declaration.created_at,
            ),
        )


def _memory_state(database: Database, subject_id: str, audit_id: UUID) -> dict[str, int]:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM ynoy.bootstrap_declarations
               WHERE subject_id = %s) AS declarations,
              (SELECT count(*) FROM ynoy.claim_candidates
               WHERE subject_id = %s) AS candidates,
              (SELECT count(*) FROM ynoy.memory_corrections
               WHERE subject_id = %s) AS corrections,
              (SELECT count(*) FROM ynoy.audit_receipts
               WHERE record_id = %s) AS audits
            """,
            (subject_id, subject_id, subject_id, audit_id),
        ).fetchone()
    assert row is not None
    return {name: int(row[name]) for name in row}


def _target_state(database: Database, record_id: UUID) -> tuple[str, UUID | None]:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT status, superseded_by FROM ynoy.bootstrap_declarations WHERE record_id = %s",
            (record_id,),
        ).fetchone()
    assert row is not None
    return str(row["status"]), row["superseded_by"]


def test_d0_add_to_legacy_d3_subject_rolls_back_atomically(test_database: Database) -> None:
    subject_id = f"legacy-d3-{uuid4()}"
    legacy = _declaration(subject_id, synthetic=False)
    incoming = _declaration(subject_id, synthetic=True)
    audit = _audit(DataClass.PUBLIC_SYNTHETIC)
    _seed_bootstrap_directly(test_database, legacy)
    before = _memory_state(test_database, subject_id, audit.record_id)

    with pytest.raises(PolicyViolation) as blocked:
        MemoryMutationRepository(test_database).add_bootstrap_declarations((incoming,), audit)

    assert blocked.value.code == "synthetic_subject_contains_private_identity"
    assert _memory_state(test_database, subject_id, audit.record_id) == before
    assert before == {"declarations": 1, "candidates": 0, "corrections": 0, "audits": 0}


def test_d0_replacement_of_d3_target_rolls_back_atomically(test_database: Database) -> None:
    subject_id = f"replacement-d3-{uuid4()}"
    target = _declaration(subject_id, synthetic=False)
    replacement = _declaration(subject_id, synthetic=True)
    audit = _audit(DataClass.PUBLIC_SYNTHETIC)
    _seed_bootstrap_directly(test_database, target)
    before = _memory_state(test_database, subject_id, audit.record_id)
    target_before = _target_state(test_database, target.record_id)

    with pytest.raises(PolicyViolation) as blocked:
        MemoryMutationRepository(test_database).correct(
            target_record_id=target.record_id,
            reason="cross-plane replacement must fail",
            audit_receipt=audit,
            replacement=replacement,
            subject_id=subject_id,
        )

    assert blocked.value.code == "replacement_data_class_mismatch"
    assert _memory_state(test_database, subject_id, audit.record_id) == before
    assert _target_state(test_database, target.record_id) == target_before == ("confirmed", None)


def test_d3_candidate_into_d0_subject_rolls_back_atomically(test_database: Database) -> None:
    subject_id = f"candidate-d0-{uuid4()}"
    declaration = _declaration(subject_id, synthetic=True)
    mutations = MemoryMutationRepository(test_database)
    mutations.add_bootstrap_declarations((declaration,), _audit(DataClass.PUBLIC_SYNTHETIC))
    candidate = _candidate(subject_id)
    audit = _audit(DataClass.DERIVED_IDENTITY)
    before = _memory_state(test_database, subject_id, audit.record_id)

    with pytest.raises(PolicyViolation) as blocked:
        mutations.add_claim_candidates((candidate,), audit)

    assert blocked.value.code == "private_subject_contains_synthetic_identity"
    assert _memory_state(test_database, subject_id, audit.record_id) == before
    assert before["declarations"] == 1 and before["candidates"] == before["audits"] == 0


def test_inference_gates_and_filters_cross_plane_evidence(test_database: Database) -> None:
    subject_id = f"contaminated-{uuid4()}"
    candidate = _candidate(subject_id)
    MemoryMutationRepository(test_database).add_claim_candidates(
        (candidate,), _audit(DataClass.DERIVED_IDENTITY)
    )
    declaration = _declaration(subject_id, synthetic=True)
    _seed_bootstrap_directly(test_database, declaration)
    synthetic = MemoryRepository(test_database, inference_data_class=DataClass.PUBLIC_SYNTHETIC)
    private = MemoryRepository(test_database, inference_data_class=DataClass.DERIVED_IDENTITY)

    scope = ScopeRef(person_id=subject_id)
    with pytest.raises(PolicyViolation) as synthetic_blocked:
        select_evidence(synthetic, task="reversible evidence", scope=scope, subject_id=subject_id)
    with pytest.raises(PolicyViolation) as real_blocked:
        select_evidence(private, task="reversible evidence", scope=scope, subject_id=subject_id)
    assert synthetic_blocked.value.code == "synthetic_mode_contains_private_data"
    assert real_blocked.value.code == "real_mode_contains_synthetic_identity"


def test_memory_repository_requires_explicit_inference_plane(test_database: Database) -> None:
    with pytest.raises(TypeError):
        MemoryRepository(test_database)  # type: ignore[call-arg]


def test_legacy_d3_bootstrap_is_blocked_from_private_inference(
    test_database: Database,
) -> None:
    subject_id = f"legacy-inference-{uuid4()}"
    _seed_bootstrap_directly(test_database, _declaration(subject_id, synthetic=False))
    reader = MemoryRepository(test_database, inference_data_class=DataClass.DERIVED_IDENTITY)

    for method_name in ("list_bootstrap_declarations", "list_claim_candidates"):
        with pytest.raises(PolicyViolation) as blocked:
            getattr(reader, method_name)(subject_id=subject_id)
        assert blocked.value.code == "real_declaration_provenance_unverified"


def test_inspection_repository_is_plane_filtered_and_not_an_inference_reader(
    test_database: Database,
) -> None:
    subject_id = f"inspection-mixed-{uuid4()}"
    candidate = _candidate(subject_id)
    MemoryMutationRepository(test_database).add_claim_candidates(
        (candidate,), _audit(DataClass.DERIVED_IDENTITY)
    )
    declaration = _declaration(subject_id, synthetic=True)
    _seed_bootstrap_directly(test_database, declaration)
    public = MemoryInspectionRepository(test_database, data_class=DataClass.PUBLIC_SYNTHETIC)
    private = MemoryInspectionRepository(test_database, data_class=DataClass.DERIVED_IDENTITY)

    assert [
        item.record_id for item in public.inspect_bootstrap_declarations(subject_id=subject_id)
    ] == [declaration.record_id]
    assert public.inspect_claim_candidates(subject_id=subject_id) == []
    assert private.inspect_bootstrap_declarations(subject_id=subject_id) == []
    assert [item.record_id for item in private.inspect_claim_candidates(subject_id=subject_id)] == [
        candidate.record_id
    ]
    assert not hasattr(public, "list_bootstrap_declarations")
    assert not hasattr(public, "list_claim_candidates")
