from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from conftest import synthetic_audit

from ynoy.bootstrap import load_bootstrap
from ynoy.corpus import ChatGPTZipAdapter, create_ingestion_approval
from ynoy.errors import StorageError
from ynoy.models import BootstrapDeclaration, CandidateKind, DataClass
from ynoy.storage import (
    AuditRepository,
    CorpusRepository,
    Database,
    ErasureRepository,
    MemoryMutationRepository,
    MemoryRepository,
)

pytestmark = pytest.mark.integration


def _ingest_synthetic_source(database: Database, archive_path: Path) -> tuple[str, int, int]:
    adapter = ChatGPTZipAdapter()
    manifest = adapter.inventory(archive_path, synthetic=True)
    approval = create_ingestion_approval(
        manifest,
        allowed_operations=("ingest",),
        retention_days=1,
        third_party_reviewed=False,
    )
    repository = CorpusRepository(database)
    repository.save_inventory(manifest, synthetic_audit(event_type="inventory"))
    repository.save_approval(approval, synthetic_audit(event_type="approval"))
    run_id = uuid4()
    inserted, receipt = repository.ingest_events(
        adapter.iter_events(archive_path, manifest=manifest, import_run_id=run_id),
        lambda count: adapter.build_receipt(
            manifest=manifest, import_run_id=run_id, normalized_count=count
        ),
        lambda receipt: synthetic_audit(event_type="ingest", artifact_id=str(receipt.record_id)),
    )
    return manifest.source_archive_sha256, inserted, receipt.normalized_event_count


def test_migration_is_idempotent_and_versions_are_exact(test_database: Database) -> None:
    result = test_database.migrate()
    status = test_database.status()
    assert result["postgres_version"] == "18.4"
    assert result["pgvector_version"] == "0.8.2"
    assert result["applied_migrations"] == []
    assert status["postgres_version"] == "18.4"
    assert status["pgvector_version"] == "0.8.2"
    assert status["migration_current"] is True
    assert status["missing_migrations"] == []
    assert status["unexpected_migrations"] == []
    assert status["mismatched_migrations"] == []
    assert status["expected_migration_count"] == status["applied_migration_count"]
    assert int(status["migration_count"]) >= 2
    with test_database.connect() as connection:
        row = connection.execute(
            "SELECT count(*) AS count FROM ynoy.schema_migrations "
            "WHERE migration_id = '002_security_lineage_hardening.sql'"
        ).fetchone()
    assert row is not None and row["count"] == 1


def test_audit_receipts_are_append_only(test_database: Database) -> None:
    receipt = synthetic_audit(event_type="report", reason_code="synthetic_append_only_test")
    AuditRepository(test_database).append(receipt)
    with pytest.raises(StorageError):
        with test_database.connect() as connection:
            connection.execute(
                "UPDATE ynoy.audit_receipts SET status = 'failure' WHERE record_id = %s",
                (receipt.record_id,),
            )
    with pytest.raises(StorageError):
        with test_database.connect() as connection:
            connection.execute(
                "DELETE FROM ynoy.audit_receipts WHERE record_id = %s",
                (receipt.record_id,),
            )
    with pytest.raises(StorageError):
        with test_database.connect() as connection:
            connection.execute("TRUNCATE ynoy.audit_receipts")
    with test_database.connect() as connection:
        row = connection.execute(
            "SELECT status FROM ynoy.audit_receipts WHERE record_id = %s",
            (receipt.record_id,),
        ).fetchone()
    assert row is not None and row["status"] == "success"


def test_corpus_ingestion_is_idempotent(test_database: Database, make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip()
    source_id, inserted, normalized = _ingest_synthetic_source(test_database, archive_path)
    assert inserted == normalized == 3
    adapter = ChatGPTZipAdapter()
    manifest = adapter.inventory(archive_path, synthetic=True)
    repository = CorpusRepository(test_database)
    run_id = uuid4()
    replayed, replay_receipt = repository.ingest_events(
        adapter.iter_events(archive_path, manifest=manifest, import_run_id=run_id),
        lambda count: adapter.build_receipt(
            manifest=manifest, import_run_id=run_id, normalized_count=count
        ),
        lambda receipt: synthetic_audit(event_type="ingest", artifact_id=str(receipt.record_id)),
    )
    assert replayed == 0
    assert replay_receipt.normalized_event_count == normalized
    with test_database.connect() as connection:
        row = connection.execute(
            "SELECT count(*) AS count FROM ynoy.source_events WHERE source_id = %s",
            (source_id,),
        ).fetchone()
    assert row is not None and row["count"] == normalized


def test_bootstrap_import_and_correction_are_explicit_and_idempotent(
    test_database: Database, tmp_path: Path
) -> None:
    source = tmp_path / "bootstrap.json"
    unique_statement = f"decision:reject synthetic-run:{uuid4()}"
    source.write_text(
        json.dumps([{"statement": unique_statement, "synthetic": True}]),
        encoding="utf-8",
    )
    declarations = load_bootstrap(source, synthetic=True)
    mutations = MemoryMutationRepository(test_database)
    reader = MemoryRepository(test_database, inference_data_class=DataClass.PUBLIC_SYNTHETIC)
    assert mutations.add_bootstrap_declarations(declarations, synthetic_audit()) == 1
    assert mutations.add_bootstrap_declarations(declarations, synthetic_audit()) == 0
    replacement = BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement="decision:correct",
        source_name="replacement-fixture.json",
        data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )
    result = mutations.correct(
        target_record_id=declarations[0].record_id,
        reason="synthetic correction",
        audit_receipt=synthetic_audit(),
        replacement=replacement,
    )
    assert result["status"] == "superseded"
    active = reader.list_bootstrap_declarations()
    assert replacement.record_id in {item.record_id for item in active}
    assert declarations[0].record_id not in {item.record_id for item in active}
    all_records = reader.list_bootstrap_declarations(include_inactive=True)
    statuses = {item.record_id: item.status.value for item in all_records}
    assert statuses[declarations[0].record_id] == "superseded"


def test_erasure_cascade_is_resumable_and_leaves_content_free_tombstone(
    test_database: Database, make_chatgpt_zip
) -> None:
    source_id, inserted, _ = _ingest_synthetic_source(test_database, make_chatgpt_zip())
    repository = ErasureRepository(test_database)
    plan = repository.plan(source_id=source_id)
    plan_id = UUID(str(plan["plan_id"]))
    digest = str(plan["plan_sha256"])
    first = repository.confirm_database(plan_id=plan_id, plan_sha256=digest)
    resumed = repository.confirm_database(plan_id=plan_id, plan_sha256=digest)
    assert first["database_deleted"] is True
    assert first["deleted_record_count"] >= inserted
    assert resumed == first
    repository.finalize(plan_id=plan_id, plan_sha256=digest)
    with test_database.connect() as connection:
        counts = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM ynoy.source_events WHERE source_id = %s) AS events,
              (SELECT count(*) FROM ynoy.inventory_manifests
               WHERE source_archive_sha256 = %s) AS manifests,
              (SELECT count(*) FROM ynoy.audit_receipts
               WHERE reason_code = 'local_dependency_cascade_deleted'
                 AND opaque_input_ids @> ARRAY[%s]) AS tombstones,
              (SELECT count(*) FROM ynoy.audit_receipts
               WHERE reason_code = 'local_database_deleted_pending_artifact_cleanup'
                 AND opaque_input_ids @> ARRAY[%s]) AS database_delete_receipts
            """,
            (source_id, source_id, str(plan_id), str(plan_id)),
        ).fetchone()
    assert counts is not None
    assert counts["events"] == 0 and counts["manifests"] == 0
    assert counts["tombstones"] == 1
    assert counts["database_delete_receipts"] == 1
