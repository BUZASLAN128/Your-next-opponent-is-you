from __future__ import annotations

from psycopg import Connection

from ynoy.models import AuditReceipt
from ynoy.storage.database import Database, Row


class AuditRepository:
    def __init__(self, database: Database):
        self.database = database

    def append(self, receipt: AuditReceipt) -> None:
        with self.database.connect() as connection:
            insert_audit_receipt(connection, receipt)


def insert_audit_receipt(connection: Connection[Row], receipt: AuditReceipt) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.audit_receipts (
            record_id, event_type, actor_class, policy_version, parser_version,
            config_version, opaque_input_ids, input_count, data_classes,
            decision, reason_code, destination, retention_class, artifact_id,
            status, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            receipt.record_id,
            receipt.event_type,
            receipt.actor_class,
            receipt.policy_version,
            receipt.parser_version,
            receipt.config_version,
            list(receipt.opaque_input_ids),
            receipt.input_count,
            [item.value for item in receipt.data_classes],
            receipt.decision,
            receipt.reason_code,
            receipt.destination,
            receipt.retention_class,
            receipt.artifact_id,
            receipt.status,
            receipt.created_at,
        ),
    )
