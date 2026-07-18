from __future__ import annotations

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.errors import DataValidationError
from ynoy.models import AuditReceipt, CodexCorpusApproval, CodexSnapshotReceipt
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database, Row


class CorpusVaultRepository:
    def __init__(self, database: Database):
        self.database = database

    def save_approval(
        self,
        approval: CodexCorpusApproval,
        audit: AuditReceipt,
        *,
        synthetic: bool,
    ) -> bool:
        safe = CodexCorpusApproval.model_validate(approval.model_dump(mode="python"))
        with self.database.connect() as connection:
            inserted = connection.execute(
                """
                INSERT INTO ynoy.codex_corpus_approvals (
                    record_id, manifest_id, manifest_sha256, approval_sha256,
                    allowed_operations, third_party_reviewed, synthetic, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO NOTHING
                """,
                (
                    safe.record_id,
                    safe.manifest_id,
                    safe.manifest_sha256,
                    safe.approval_sha256,
                    list(safe.allowed_operations),
                    safe.third_party_reviewed,
                    synthetic,
                    safe.created_at,
                ),
            ).rowcount
            if inserted:
                insert_audit_receipt(connection, audit)
        return bool(inserted)

    def save_snapshot(self, receipt: CodexSnapshotReceipt, audit: AuditReceipt) -> bool:
        safe = CodexSnapshotReceipt.model_validate(receipt.model_dump(mode="python"))
        with self.database.connect() as connection:
            if _receipt_exists(connection, safe):
                return False
            _upsert_snapshot(connection, safe)
            _insert_blobs(connection, safe)
            _replace_files(connection, safe)
            _insert_receipt(connection, safe)
            insert_audit_receipt(connection, audit)
        return True

    def status(self, snapshot_id: object) -> dict[str, object]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ynoy.corpus_snapshots WHERE snapshot_id = %s",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise DataValidationError("codex_snapshot_not_found", "Codex snapshot was not found.")
        return dict(row)


def _receipt_exists(connection: Connection[Row], receipt: CodexSnapshotReceipt) -> bool:
    row = connection.execute(
        "SELECT receipt_sha256 FROM ynoy.corpus_snapshot_receipts WHERE record_id = %s",
        (receipt.record_id,),
    ).fetchone()
    if row is None:
        return False
    if row["receipt_sha256"] != receipt.receipt_sha256:
        raise DataValidationError(
            "codex_snapshot_receipt_conflict",
            "Snapshot receipt identifier already binds different state.",
        )
    return True


def _upsert_snapshot(connection: Connection[Row], receipt: CodexSnapshotReceipt) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.corpus_snapshots (
            snapshot_id, manifest_id, manifest_sha256, approval_id, latest_receipt_id,
            source_data_class, synthetic, status, expected_file_count, expected_bytes,
            vaulted_file_count, vaulted_bytes, deferred_file_count, error_file_count,
            updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_id) DO UPDATE SET
            latest_receipt_id = EXCLUDED.latest_receipt_id,
            status = EXCLUDED.status,
            vaulted_file_count = EXCLUDED.vaulted_file_count,
            vaulted_bytes = EXCLUDED.vaulted_bytes,
            deferred_file_count = EXCLUDED.deferred_file_count,
            error_file_count = EXCLUDED.error_file_count,
            updated_at = EXCLUDED.updated_at
        """,
        (
            receipt.snapshot_id,
            receipt.manifest_id,
            receipt.manifest_sha256,
            receipt.approval_id,
            receipt.record_id,
            receipt.source_data_class.value,
            receipt.synthetic,
            receipt.status,
            receipt.expected_file_count,
            receipt.expected_bytes,
            receipt.vaulted_file_count,
            receipt.vaulted_bytes,
            receipt.deferred_file_count,
            receipt.error_file_count,
            receipt.created_at,
        ),
    )


def _insert_blobs(connection: Connection[Row], receipt: CodexSnapshotReceipt) -> None:
    for item in receipt.files:
        if item.blob_sha256 is not None:
            connection.execute(
                """
                INSERT INTO ynoy.corpus_blobs (blob_sha256, byte_count, created_at)
                VALUES (%s, %s, %s) ON CONFLICT (blob_sha256) DO NOTHING
                """,
                (item.blob_sha256, item.vaulted_bytes, receipt.created_at),
            )


def _replace_files(connection: Connection[Row], receipt: CodexSnapshotReceipt) -> None:
    connection.execute(
        "DELETE FROM ynoy.corpus_snapshot_files WHERE snapshot_id = %s",
        (receipt.snapshot_id,),
    )
    for item in receipt.files:
        connection.execute(
            """
            INSERT INTO ynoy.corpus_snapshot_files (
                snapshot_id, source_key, partition, expected_bytes, status,
                blob_sha256, vaulted_bytes, error_code
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                receipt.snapshot_id,
                item.source_key,
                item.partition,
                item.expected_bytes,
                item.status,
                item.blob_sha256,
                item.vaulted_bytes,
                item.error_code,
            ),
        )


def _insert_receipt(connection: Connection[Row], receipt: CodexSnapshotReceipt) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.corpus_snapshot_receipts (
            record_id, snapshot_id, previous_receipt_sha256,
            receipt_sha256, record, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            receipt.record_id,
            receipt.snapshot_id,
            receipt.previous_receipt_sha256,
            receipt.receipt_sha256,
            Jsonb(receipt.model_dump(mode="json")),
            receipt.created_at,
        ),
    )
