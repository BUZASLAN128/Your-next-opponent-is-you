from __future__ import annotations

from time import monotonic
from uuid import UUID, uuid4

import pytest
from conftest import synthetic_audit

from ynoy.errors import PolicyViolation
from ynoy.models import BootstrapDeclaration, CandidateKind, DataClass, ScopeRef
from ynoy.storage import Database, MemoryMutationRepository

pytestmark = pytest.mark.integration


def _declaration(subject_id: str) -> BootstrapDeclaration:
    return BootstrapDeclaration(
        subject_id=subject_id,
        kind=CandidateKind.PREFERENCE,
        statement="Synthetic contention probe.",
        scope=ScopeRef(person_id=subject_id),
        source_name="contention.json",
        data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _mutation_state(database: Database, declaration_id: UUID, audit_id: UUID) -> tuple[int, int]:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM ynoy.bootstrap_declarations
               WHERE record_id = %s) AS declarations,
              (SELECT count(*) FROM ynoy.audit_receipts
               WHERE record_id = %s) AS audits
            """,
            (declaration_id, audit_id),
        ).fetchone()
    assert row is not None
    return int(row["declarations"]), int(row["audits"])


def test_subject_lock_contention_fails_promptly_without_partial_writes(
    test_database: Database,
) -> None:
    subject_id = f"contention-{uuid4()}"
    declaration = _declaration(subject_id)
    audit = synthetic_audit()
    before = _mutation_state(test_database, declaration.record_id, audit.record_id)

    with test_database.connect() as holder:
        lock = holder.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS acquired",
            (f"ynoy:identity-plane:{subject_id}",),
        ).fetchone()
        assert lock is not None and lock["acquired"] is True

        started = monotonic()
        with pytest.raises(PolicyViolation) as blocked:
            MemoryMutationRepository(test_database).add_bootstrap_declarations(
                (declaration,), audit
            )
        elapsed = monotonic() - started

    assert blocked.value.code == "identity_subject_busy"
    assert elapsed < 2.0
    assert before == (0, 0)
    assert _mutation_state(test_database, declaration.record_id, audit.record_id) == before
