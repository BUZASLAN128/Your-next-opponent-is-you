from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from conftest import synthetic_audit

from ynoy.errors import PolicyViolation
from ynoy.models import (
    AuditReceipt,
    ClaimHolder,
    DataClass,
    ScopeRef,
    SourceAuthority,
    SourceEvent,
    SourceReceipt,
    Speaker,
)
from ynoy.storage import CorpusRepository, Database
from ynoy.util import sha256_text

pytestmark = pytest.mark.integration


def _event(
    *,
    subject_id: str,
    import_run_id: UUID,
    source_id: str,
    event_id: str,
    data_class: DataClass,
) -> SourceEvent:
    content = f"{data_class.value} identity-plane event"
    return SourceEvent(
        import_run_id=import_run_id,
        source_id=source_id,
        source_locator=f"fixture://{event_id}",
        conversation_id=f"conversation-{subject_id}",
        branch_id="main",
        event_id=event_id,
        speaker=Speaker.USER,
        claim_holder=ClaimHolder.REPRESENTED_USER,
        source_authority=SourceAuthority.EXPLICIT_USER_STATEMENT,
        data_class=data_class,
        content=content,
        content_sha256=sha256_text(content),
        origin_cluster_id=f"cluster-{event_id}",
        scope=ScopeRef(person_id=subject_id),
    )


def _ingestion_state(
    database: Database,
    *,
    import_run_id: UUID,
    receipt_id: UUID,
    audit_id: UUID,
) -> tuple[int, int, int]:
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM ynoy.source_events
               WHERE import_run_id = %s) AS events,
              (SELECT count(*) FROM ynoy.source_receipts
               WHERE record_id = %s) AS receipts,
              (SELECT count(*) FROM ynoy.audit_receipts
               WHERE record_id = %s) AS audits
            """,
            (import_run_id, receipt_id, audit_id),
        ).fetchone()
    assert row is not None
    return int(row["events"]), int(row["receipts"]), int(row["audits"])


def _mixed_batch() -> tuple[tuple[SourceEvent, ...], SourceReceipt, AuditReceipt]:
    subject_id = f"mixed-ingestion-{uuid4()}"
    import_run_id = uuid4()
    source_id = f"source-{uuid4()}"
    events = (
        _event(
            subject_id=subject_id,
            import_run_id=import_run_id,
            source_id=source_id,
            event_id="synthetic",
            data_class=DataClass.PUBLIC_SYNTHETIC,
        ),
        _event(
            subject_id=subject_id,
            import_run_id=import_run_id,
            source_id=source_id,
            event_id="private",
            data_class=DataClass.RAW_CORPUS,
        ),
    )
    receipt = SourceReceipt(
        import_run_id=import_run_id,
        source_id=source_id,
        adapter="pytest",
        parser_version="1.0",
        source_archive_sha256=sha256_text(source_id),
        normalized_event_count=2,
        excluded_event_count=0,
        speaker_counts={"user": 2},
        status="complete",
    )
    audit: AuditReceipt = synthetic_audit(event_type="ingest").model_copy(
        update={"data_classes": (DataClass.PUBLIC_SYNTHETIC, DataClass.RAW_CORPUS)}
    )
    return events, receipt, audit


def test_mixed_identity_plane_batch_rejects_without_partial_writes(
    test_database: Database,
) -> None:
    events, receipt, audit = _mixed_batch()
    factory_calls: list[str] = []

    def receipt_factory(count: int) -> SourceReceipt:
        factory_calls.append(f"receipt:{count}")
        return receipt

    def audit_factory(_: SourceReceipt) -> AuditReceipt:
        factory_calls.append("audit")
        return audit

    with pytest.raises(PolicyViolation) as blocked:
        CorpusRepository(test_database).ingest_events(
            events,
            receipt_factory,
            audit_factory,
            batch_size=2,
        )

    assert blocked.value.code == "identity_batch_mixes_synthetic_and_private"
    assert factory_calls == []
    assert _ingestion_state(
        test_database,
        import_run_id=receipt.import_run_id,
        receipt_id=receipt.record_id,
        audit_id=audit.record_id,
    ) == (0, 0, 0)
