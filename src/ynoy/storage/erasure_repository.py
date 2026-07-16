from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.constants import SCHEMA_VERSION
from ynoy.errors import DataValidationError
from ynoy.models import AuditReceipt
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database, Row
from ynoy.storage.erasure_operations import (
    assert_current_targets,
    delete_targets,
    target_counts,
    target_ids,
)
from ynoy.util import canonical_sha256, new_id, utc_now


class ErasureRepository:
    def __init__(self, database: Database):
        self.database = database

    def plan(self, *, source_id: str, ttl_minutes: int = 30) -> dict[str, object]:
        with self.database.connect() as connection:
            targets = target_ids(connection, source_id)
            if not targets:
                raise DataValidationError(
                    "erasure_source_not_found", "No private records match this source ID."
                )
            counts = target_counts(connection, source_id, targets)
            plan_id = new_id()
            expires_at = utc_now() + timedelta(minutes=ttl_minutes)
            payload = {
                "plan_id": str(plan_id),
                "source_id": source_id,
                "target_record_ids": [str(value) for value in targets],
                "target_counts": counts,
                "expires_at": expires_at.isoformat(),
            }
            plan_sha256 = canonical_sha256(payload)
            connection.execute(
                """
                INSERT INTO ynoy.erasure_plans (
                    record_id, source_id, target_record_ids, target_counts,
                    plan_sha256, expires_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (plan_id, source_id, targets, Jsonb(counts), plan_sha256, expires_at, utc_now()),
            )
            _append_erasure_plan_receipt(connection, plan_id, len(targets))
        return {**payload, "plan_sha256": plan_sha256}

    def confirm_database(self, *, plan_id: UUID, plan_sha256: str) -> dict[str, object]:
        with self.database.connect() as connection:
            plan = _lock_plan(connection, plan_id, plan_sha256)
            target_ids = list(plan["target_record_ids"])
            source_id = str(plan["source_id"])
            if plan["confirmed_at"] is None:
                assert_current_targets(connection, source_id, target_ids)
                delete_targets(connection, source_id, target_ids)
                connection.execute(
                    "UPDATE ynoy.erasure_plans SET confirmed_at = %s WHERE record_id = %s",
                    (utc_now(), plan_id),
                )
                _append_database_delete_receipt(connection, plan_id, len(target_ids))
        return {
            "plan_id": str(plan_id),
            "source_id": source_id,
            "deleted_record_count": len(target_ids),
            "target_counts": plan["target_counts"],
            "artifact_ids": [str(value) for value in target_ids],
            "database_deleted": True,
        }

    def finalize(self, *, plan_id: UUID, plan_sha256: str) -> None:
        with self.database.connect() as connection:
            plan = _lock_plan(connection, plan_id, plan_sha256)
            if plan["confirmed_at"] is None:
                raise DataValidationError(
                    "erasure_database_not_confirmed",
                    "Database deletion must complete before artifact cleanup is finalized.",
                )
            _append_tombstone(connection, plan_id, len(plan["target_record_ids"]))
            connection.execute("DELETE FROM ynoy.erasure_plans WHERE record_id = %s", (plan_id,))


def _lock_plan(connection: Connection[Row], plan_id: UUID, digest: str) -> Row:
    plan = connection.execute(
        """
        SELECT source_id, target_record_ids, target_counts, plan_sha256,
               expires_at, confirmed_at
        FROM ynoy.erasure_plans WHERE record_id = %s FOR UPDATE
        """,
        (plan_id,),
    ).fetchone()
    if plan is None:
        raise DataValidationError("erasure_plan_not_found", "Erasure plan was not found.")
    if plan["confirmed_at"] is None and plan["expires_at"] <= utc_now():
        raise DataValidationError("erasure_plan_expired", "Erasure plan has expired.")
    if plan["plan_sha256"] != digest:
        raise DataValidationError(
            "erasure_plan_digest_mismatch", "Erasure confirmation digest does not match."
        )
    return plan


def _append_tombstone(connection: Connection[Row], plan_id: UUID, count: int) -> None:
    receipt = AuditReceipt(
        event_type="erasure_confirm",
        actor_class="represented_user",
        config_version=SCHEMA_VERSION,
        opaque_input_ids=(str(plan_id),),
        input_count=count,
        decision="complete",
        reason_code="local_dependency_cascade_deleted",
        status="success",
    )
    insert_audit_receipt(connection, receipt)


def _append_database_delete_receipt(connection: Connection[Row], plan_id: UUID, count: int) -> None:
    receipt = AuditReceipt(
        event_type="erasure_confirm",
        actor_class="represented_user",
        config_version=SCHEMA_VERSION,
        opaque_input_ids=(str(plan_id),),
        input_count=count,
        decision="partial",
        reason_code="local_database_deleted_pending_artifact_cleanup",
        status="partial",
    )
    insert_audit_receipt(connection, receipt)


def _append_erasure_plan_receipt(connection: Connection[Row], plan_id: UUID, count: int) -> None:
    receipt = AuditReceipt(
        event_type="erasure_plan",
        actor_class="represented_user",
        config_version=SCHEMA_VERSION,
        opaque_input_ids=(str(plan_id),),
        input_count=count,
        decision="allow",
        reason_code="dependency_erasure_plan_created",
        status="success",
    )
    insert_audit_receipt(connection, receipt)
