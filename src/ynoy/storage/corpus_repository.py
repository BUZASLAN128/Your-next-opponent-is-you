from __future__ import annotations

from collections.abc import Callable, Iterable

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.errors import PolicyViolation
from ynoy.models import (
    AuditReceipt,
    DataClass,
    IngestionApproval,
    InventoryManifest,
    SourceEvent,
    SourceReceipt,
)
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database, Row
from ynoy.storage.memory_plane import require_subject_plane
from ynoy.util import batched


class CorpusRepository:
    def __init__(self, database: Database):
        self.database = database

    def save_inventory(self, manifest: InventoryManifest, audit_receipt: AuditReceipt) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO ynoy.inventory_manifests
                    (record_id, created_at, source_archive_sha256, manifest_sha256,
                     source_data_class, synthetic, record)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO NOTHING
                """,
                (
                    manifest.record_id,
                    manifest.created_at,
                    manifest.source_archive_sha256,
                    manifest.manifest_sha256,
                    manifest.source_data_class.value,
                    manifest.synthetic,
                    Jsonb(manifest.model_dump(mode="json")),
                ),
            )
            insert_audit_receipt(connection, audit_receipt)

    def save_approval(self, approval: IngestionApproval, audit_receipt: AuditReceipt) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO ynoy.ingestion_approvals
                    (record_id, manifest_id, created_at, approval_sha256, record)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO NOTHING
                """,
                (
                    approval.record_id,
                    approval.manifest_id,
                    approval.created_at,
                    approval.approval_sha256,
                    Jsonb(approval.model_dump(mode="json")),
                ),
            )
            insert_audit_receipt(connection, audit_receipt)

    def ingest_events(
        self,
        events: Iterable[SourceEvent],
        receipt_factory: Callable[[int], SourceReceipt],
        audit_factory: Callable[[SourceReceipt], AuditReceipt],
        *,
        batch_size: int = 500,
    ) -> tuple[int, SourceReceipt]:
        inserted = 0
        normalized = 0
        with self.database.connect() as connection:
            for event_batch in batched(events, batch_size):
                normalized += len(event_batch)
                _require_event_planes(connection, event_batch)
                for event in event_batch:
                    inserted += _insert_event(connection, event)
            receipt = receipt_factory(normalized)
            _save_receipt(connection, receipt)
            insert_audit_receipt(connection, audit_factory(receipt))
        return inserted, receipt


def _require_event_planes(connection: Connection[Row], events: Iterable[SourceEvent]) -> None:
    by_subject: dict[str, set[DataClass]] = {}
    for event in events:
        by_subject.setdefault(event.scope.person_id, set()).add(event.data_class)
    for subject_id in sorted(by_subject):
        classes = by_subject[subject_id]
        has_synthetic = DataClass.PUBLIC_SYNTHETIC in classes
        has_private = any(item != DataClass.PUBLIC_SYNTHETIC for item in classes)
        if has_synthetic and has_private:
            raise PolicyViolation(
                "identity_batch_mixes_synthetic_and_private",
                "One ingestion batch cannot mix synthetic and private identity data.",
            )
        require_subject_plane(
            connection,
            subject_id=subject_id,
            data_class=min(classes, key=lambda item: item.value),
        )


def _insert_event(connection: Connection[Row], event: SourceEvent) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ynoy.source_events (
            record_id, import_run_id, source_id, source_locator, conversation_id,
            branch_id, event_id, parent_event_id, speaker, claim_holder,
            source_authority, data_class, event_time, content, content_sha256,
            origin_cluster_id, scope, metadata, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (source_id, event_id) DO NOTHING
        """,
        (
            event.record_id,
            event.import_run_id,
            event.source_id,
            event.source_locator,
            event.conversation_id,
            event.branch_id,
            event.event_id,
            event.parent_event_id,
            event.speaker.value,
            event.claim_holder.value,
            event.source_authority.value,
            event.data_class.value,
            event.event_time,
            event.content,
            event.content_sha256,
            event.origin_cluster_id,
            Jsonb(event.scope.model_dump(mode="json")),
            Jsonb(event.metadata),
            event.created_at,
        ),
    )
    return cursor.rowcount


def _save_receipt(connection: Connection[Row], receipt: SourceReceipt) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.source_receipts
            (record_id, import_run_id, source_id, source_archive_sha256,
             status, record, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (import_run_id) DO UPDATE SET
            status = EXCLUDED.status,
            record = EXCLUDED.record
        """,
        (
            receipt.record_id,
            receipt.import_run_id,
            receipt.source_id,
            receipt.source_archive_sha256,
            receipt.status,
            Jsonb(receipt.model_dump(mode="json")),
            receipt.created_at,
        ),
    )
