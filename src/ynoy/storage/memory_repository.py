from __future__ import annotations

from datetime import datetime

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import BootstrapDeclaration, CanonicalClaim, ClaimCandidate, DataClass
from ynoy.storage.canonical_repository import CanonicalClaimRepository
from ynoy.storage.database import Database

_IDENTITY_PLANES = {DataClass.PUBLIC_SYNTHETIC, DataClass.DERIVED_IDENTITY}


class MemoryRepository:
    """Plane-bound memory reader safe for inference."""

    def __init__(self, database: Database, *, inference_data_class: DataClass):
        self.database = database
        self.inference_data_class = _require_identity_plane(inference_data_class)

    def assert_inference_ready(self, *, subject_id: str = "self") -> None:
        if self.inference_data_class == DataClass.PUBLIC_SYNTHETIC:
            self.assert_synthetic_only(subject_id=subject_id)
        else:
            self.assert_private_inference_ready(subject_id=subject_id)

    def assert_synthetic_only(self, *, subject_id: str = "self") -> None:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT data_class FROM ynoy.bootstrap_declarations
                WHERE subject_id = %s
                UNION SELECT 'D3' FROM ynoy.claim_candidates WHERE subject_id = %s
                UNION SELECT DISTINCT data_class FROM ynoy.canonical_claims
                WHERE subject_id = %s
                UNION SELECT DISTINCT data_class FROM ynoy.source_events
                WHERE scope ->> 'person_id' = %s
                """,
                (subject_id, subject_id, subject_id, subject_id),
            ).fetchall()
        blocked = sorted(str(row["data_class"]) for row in rows if row["data_class"] != "D0")
        if blocked:
            raise PolicyViolation(
                "synthetic_mode_contains_private_data",
                "Synthetic mode cannot read a subject that has non-D0 records.",
                details={"blocked_classes": blocked},
            )

    def assert_private_inference_ready(self, *, subject_id: str = "self") -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                  EXISTS (
                    SELECT 1 FROM ynoy.bootstrap_declarations
                    WHERE subject_id = %s AND data_class = 'D0'
                    UNION ALL
                    SELECT 1 FROM ynoy.source_events
                    WHERE scope ->> 'person_id' = %s AND data_class = 'D0'
                    UNION ALL
                    SELECT 1 FROM ynoy.canonical_claims
                    WHERE subject_id = %s AND data_class = 'D0'
                  ) AS has_synthetic,
                  EXISTS (
                    SELECT 1 FROM ynoy.bootstrap_declarations
                    WHERE subject_id = %s AND data_class = 'D3'
                  ) AS has_unverified_declaration
                """,
                (subject_id, subject_id, subject_id, subject_id),
            ).fetchone()
        if row and row["has_synthetic"]:
            raise PolicyViolation(
                "real_mode_contains_synthetic_identity",
                "Real inference cannot read a subject containing synthetic identity data.",
            )
        if row and row["has_unverified_declaration"]:
            raise PolicyViolation(
                "real_declaration_provenance_unverified",
                "Stored real declarations are blocked until adoption provenance is retained.",
            )

    def list_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]:
        self.assert_inference_ready(subject_id=subject_id)
        if self.inference_data_class == DataClass.DERIVED_IDENTITY:
            return []
        return _load_bootstrap_declarations(
            self.database,
            subject_id=subject_id,
            include_inactive=include_inactive,
            data_class=DataClass.PUBLIC_SYNTHETIC,
        )

    def list_active_canonical_claims(
        self, *, subject_id: str = "self", evaluation_time: datetime
    ) -> list[CanonicalClaim]:
        self.assert_inference_ready(subject_id=subject_id)
        return CanonicalClaimRepository(
            self.database, data_class=self.inference_data_class
        ).list_active_canonical_claims(
            subject_id=subject_id,
            evaluation_time=evaluation_time,
        )


class MemoryInspectionRepository:
    """Plane-filtered inspection reader that cannot satisfy the inference protocol."""

    def __init__(self, database: Database, *, data_class: DataClass):
        self.database = database
        self.data_class = _require_identity_plane(data_class)

    def inspect_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]:
        return _load_bootstrap_declarations(
            self.database,
            subject_id=subject_id,
            include_inactive=include_inactive,
            data_class=self.data_class,
        )

    def inspect_claim_candidates(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[ClaimCandidate]:
        if self.data_class == DataClass.PUBLIC_SYNTHETIC:
            return []
        return _load_claim_candidates(
            self.database,
            subject_id=subject_id,
            include_inactive=include_inactive,
        )

    def inspect_canonical_claims(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[CanonicalClaim]:
        return CanonicalClaimRepository(
            self.database, data_class=self.data_class
        ).inspect_canonical_claims(
            subject_id=subject_id,
            include_inactive=include_inactive,
        )


def _require_identity_plane(data_class: DataClass) -> DataClass:
    if data_class not in _IDENTITY_PLANES:
        raise DataValidationError(
            "identity_inference_plane_invalid",
            "Memory access requires an explicit D0 or D3 identity plane.",
        )
    return data_class


def _load_bootstrap_declarations(
    database: Database,
    *,
    subject_id: str,
    include_inactive: bool,
    data_class: DataClass,
) -> list[BootstrapDeclaration]:
    status_clause = "" if include_inactive else "AND status = 'confirmed'"
    with database.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT record_id, subject_id, kind, statement, scope, decision_label,
                   COALESCE(source_record_id, record_id) AS source_record_id,
                   source_name, data_class, synthetic, status, created_at
            FROM ynoy.bootstrap_declarations
            WHERE subject_id = %s AND data_class = %s {status_clause}
            ORDER BY created_at, record_id
            """,
            (subject_id, data_class.value),
        ).fetchall()
    return [BootstrapDeclaration.model_validate(dict(row)) for row in rows]


def _load_claim_candidates(
    database: Database, *, subject_id: str, include_inactive: bool
) -> list[ClaimCandidate]:
    status_clause = "" if include_inactive else "AND status IN ('proposed', 'confirmed')"
    with database.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT record_id, subject_id, claim_holder, kind, proposition, scope,
                   confidence, status, valid_from, valid_until, origin_cluster_ids,
                   revision_of, superseded_by, created_at
            FROM ynoy.claim_candidates
            WHERE subject_id = %s {status_clause}
            ORDER BY created_at, record_id
            """,
            (subject_id,),
        ).fetchall()
    return [ClaimCandidate.model_validate(dict(row)) for row in rows]
