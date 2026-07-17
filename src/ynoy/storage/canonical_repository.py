from __future__ import annotations

from datetime import datetime
from uuid import UUID

from psycopg import Connection

from ynoy.errors import DataValidationError
from ynoy.models import (
    AuditReceipt,
    CanonicalClaim,
    CanonicalClaimAdmission,
    ClaimAdmissionReceipt,
    ClaimSourceLink,
    DataClass,
)
from ynoy.scope import scope_is_active
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.canonical_writes import persist_admission
from ynoy.storage.database import Database, Row
from ynoy.storage.memory_plane import require_subject_plane


class CanonicalClaimRepository:
    def __init__(self, database: Database, *, data_class: DataClass):
        if data_class not in {DataClass.PUBLIC_SYNTHETIC, DataClass.DERIVED_IDENTITY}:
            raise DataValidationError(
                "canonical_claim_plane_invalid",
                "Canonical claims require an explicit D0 or D3 plane.",
            )
        self.database = database
        self.data_class = data_class

    def admit(self, admission: CanonicalClaimAdmission, audit: AuditReceipt) -> bool:
        safe = CanonicalClaimAdmission.model_validate(admission.model_dump(mode="python"))
        _require_admission_plane(safe, self.data_class, audit)
        with self.database.connect() as connection:
            require_subject_plane(
                connection, subject_id=safe.claim.subject_id, data_class=safe.claim.data_class
            )
            if _existing_admission_matches(connection, safe):
                return False
            persist_admission(connection, safe)
            insert_audit_receipt(connection, audit)
        return True

    def list_active_canonical_claims(
        self, *, subject_id: str = "self", evaluation_time: datetime
    ) -> list[CanonicalClaim]:
        claims = _load_claims(
            self.database,
            subject_id=subject_id,
            data_class=self.data_class,
            include_inactive=False,
        )
        return [item for item in claims if scope_is_active(item.scope, evaluation_time)]

    def inspect_canonical_claims(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[CanonicalClaim]:
        return _load_claims(
            self.database,
            subject_id=subject_id,
            data_class=self.data_class,
            include_inactive=include_inactive,
        )

    def provenance(self, claim_id: UUID) -> CanonicalClaimAdmission:
        claim = _load_one_claim(self.database, claim_id, self.data_class)
        receipt = _load_receipt(self.database, claim_id)
        links = _load_links(self.database, claim_id)
        return CanonicalClaimAdmission(claim=claim, receipt=receipt, source_links=links)


def _require_admission_plane(
    admission: CanonicalClaimAdmission, data_class: DataClass, audit: AuditReceipt
) -> None:
    if admission.claim.data_class != data_class:
        raise DataValidationError(
            "canonical_claim_plane_mismatch", "Admission does not belong to this identity plane."
        )
    if data_class not in audit.data_classes:
        raise DataValidationError(
            "canonical_claim_audit_mismatch", "Admission audit must name the canonical data class."
        )


def _existing_admission_matches(
    connection: Connection[Row], admission: CanonicalClaimAdmission
) -> bool:
    row = connection.execute(
        """
        SELECT c.claim_sha256, r.receipt_sha256,
               ARRAY(SELECT link.link_sha256 FROM ynoy.claim_source_links link
                     WHERE link.claim_id = c.record_id ORDER BY link.record_id) AS link_hashes
        FROM ynoy.canonical_claims c
        LEFT JOIN ynoy.claim_admission_receipts r ON r.claim_id = c.record_id
        WHERE c.record_id = %s
        """,
        (admission.claim.record_id,),
    ).fetchone()
    if row is None:
        return False
    expected_links = sorted(item.link_sha256 for item in admission.source_links)
    if (
        row["claim_sha256"] != admission.claim.claim_sha256
        or row["receipt_sha256"] != admission.receipt.receipt_sha256
        or sorted(row["link_hashes"] or []) != expected_links
    ):
        raise DataValidationError(
            "canonical_admission_conflict",
            "An existing canonical record has the same identifier but different evidence.",
        )
    return True


def _load_claims(
    database: Database,
    *,
    subject_id: str,
    data_class: DataClass,
    include_inactive: bool,
) -> list[CanonicalClaim]:
    status_clause = "" if include_inactive else "AND c.status = 'confirmed'"
    with database.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT c.* FROM ynoy.canonical_claims c
            WHERE c.subject_id = %s AND c.data_class = %s {status_clause}
              AND EXISTS (
                SELECT 1 FROM ynoy.claim_admission_receipts r
                WHERE r.record_id = c.admission_receipt_id AND r.claim_id = c.record_id
                  AND r.receipt_sha256 IS NOT NULL
              )
              AND cardinality(c.source_link_ids) = (
                SELECT count(*) FROM ynoy.claim_source_links l WHERE l.claim_id = c.record_id
              )
              AND NOT EXISTS (
                SELECT 1 FROM unnest(c.source_link_ids) expected(record_id)
                WHERE NOT EXISTS (
                  SELECT 1 FROM ynoy.claim_source_links l
                  WHERE l.claim_id = c.record_id AND l.record_id = expected.record_id
                )
              )
            ORDER BY c.created_at, c.record_id
            """,
            (subject_id, data_class.value),
        ).fetchall()
    return [CanonicalClaim.model_validate(dict(row)) for row in rows]


def _load_one_claim(database: Database, claim_id: UUID, data_class: DataClass) -> CanonicalClaim:
    claims = _load_claims(
        database,
        subject_id=_claim_subject(database, claim_id),
        data_class=data_class,
        include_inactive=True,
    )
    match = next((item for item in claims if item.record_id == claim_id), None)
    if match is None:
        raise DataValidationError("canonical_claim_not_found", "Canonical claim was not found.")
    return match


def _claim_subject(database: Database, claim_id: UUID) -> str:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT subject_id FROM ynoy.canonical_claims WHERE record_id = %s", (claim_id,)
        ).fetchone()
    if row is None:
        raise DataValidationError("canonical_claim_not_found", "Canonical claim was not found.")
    return str(row["subject_id"])


def _load_receipt(database: Database, claim_id: UUID) -> ClaimAdmissionReceipt:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM ynoy.claim_admission_receipts WHERE claim_id = %s", (claim_id,)
        ).fetchone()
    if row is None:
        raise DataValidationError(
            "canonical_admission_receipt_missing", "Canonical claim admission receipt is missing."
        )
    return ClaimAdmissionReceipt.model_validate(dict(row))


def _load_links(database: Database, claim_id: UUID) -> tuple[ClaimSourceLink, ...]:
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM ynoy.claim_source_links
            WHERE claim_id = %s ORDER BY character_start, character_end, record_id
            """,
            (claim_id,),
        ).fetchall()
    return tuple(ClaimSourceLink.model_validate(dict(row)) for row in rows)
