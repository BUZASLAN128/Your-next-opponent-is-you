from __future__ import annotations

import math
from collections.abc import Sequence
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.constants import DEFAULT_EMBEDDING_DIMENSIONS
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import AuditReceipt, BootstrapDeclaration, ClaimCandidate, DataClass
from ynoy.storage.audit_repository import insert_audit_receipt
from ynoy.storage.database import Database, Row
from ynoy.storage.memory_plane import require_subject_plane
from ynoy.util import new_id, utc_now


class MemoryMutationRepository:
    def __init__(self, database: Database):
        self.database = database

    def add_bootstrap_declarations(
        self,
        declarations: Sequence[BootstrapDeclaration],
        audit_receipt: AuditReceipt,
    ) -> int:
        _reject_real_declaration_persistence(declarations)
        inserted = 0
        with self.database.connect() as connection:
            _require_declaration_planes(connection, declarations)
            for declaration in declarations:
                inserted += _insert_declaration(connection, declaration, ignore_conflict=True)
            insert_audit_receipt(connection, audit_receipt)
        return inserted

    def add_claim_candidates(
        self, candidates: Sequence[ClaimCandidate], audit_receipt: AuditReceipt
    ) -> int:
        inserted = 0
        with self.database.connect() as connection:
            for subject_id in sorted({item.subject_id for item in candidates}):
                require_subject_plane(
                    connection,
                    subject_id=subject_id,
                    data_class=DataClass.DERIVED_IDENTITY,
                )
            for candidate in candidates:
                cursor = connection.execute(
                    """
                    INSERT INTO ynoy.claim_candidates (
                        record_id, subject_id, claim_holder, kind, proposition, scope,
                        confidence, status, valid_from, valid_until, origin_cluster_ids,
                        revision_of, superseded_by, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (record_id) DO NOTHING
                    """,
                    _candidate_values(candidate),
                )
                inserted += cursor.rowcount
            insert_audit_receipt(connection, audit_receipt)
        return inserted

    def save_identity_embedding(
        self,
        *,
        record_id: UUID,
        model_id: str,
        embedding: Sequence[float],
        audit_receipt: AuditReceipt,
    ) -> None:
        if len(embedding) != DEFAULT_EMBEDDING_DIMENSIONS or not all(
            math.isfinite(value) for value in embedding
        ):
            raise DataValidationError(
                "embedding_dimensions_invalid", "Identity embedding must be a finite 1024-vector."
            )
        vector = "[" + ",".join(format(value, ".9g") for value in embedding) + "]"
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO ynoy.identity_embeddings
                    (record_id, model_id, embedding, created_at)
                VALUES (%s, %s, %s::vector, %s)
                ON CONFLICT (record_id) DO UPDATE SET
                    model_id = EXCLUDED.model_id,
                    embedding = EXCLUDED.embedding,
                    created_at = EXCLUDED.created_at
                """,
                (record_id, model_id, vector, utc_now()),
            )
            insert_audit_receipt(connection, audit_receipt)

    def correct(
        self,
        *,
        target_record_id: UUID,
        reason: str,
        audit_receipt: AuditReceipt,
        replacement: BootstrapDeclaration | None = None,
        subject_id: str = "self",
    ) -> dict[str, object]:
        if replacement is not None:
            _reject_real_declaration_persistence((replacement,))
        correction_id = new_id()
        with self.database.connect() as connection:
            table, target_subject, target_class = _lock_memory_target(connection, target_record_id)
            if target_subject != subject_id:
                raise DataValidationError(
                    "memory_record_not_found", "The scoped memory record was not found."
                )
            replacement_id = _save_replacement(
                connection,
                replacement,
                subject_id,
                target_data_class=target_class,
            )
            next_status = "superseded" if replacement_id else "invalidated"
            connection.execute(
                f"UPDATE ynoy.{table} SET status = %s, superseded_by = %s WHERE record_id = %s",
                (next_status, replacement_id, target_record_id),
            )
            connection.execute(
                """
                INSERT INTO ynoy.memory_corrections
                    (record_id, target_record_id, replacement_record_id, reason,
                     subject_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (correction_id, target_record_id, replacement_id, reason, subject_id, utc_now()),
            )
            insert_audit_receipt(connection, audit_receipt)
        return {
            "correction_id": str(correction_id),
            "target_record_id": str(target_record_id),
            "replacement_record_id": str(replacement_id) if replacement_id else None,
            "status": next_status,
        }


def _reject_real_declaration_persistence(
    declarations: Sequence[BootstrapDeclaration],
) -> None:
    if any(not declaration.synthetic for declaration in declarations):
        raise PolicyViolation(
            "real_identity_persistence_unsupported",
            "Real declarations require a provenance-preserving persistence schema.",
        )


def _require_declaration_planes(
    connection: Connection[Row], declarations: Sequence[BootstrapDeclaration]
) -> None:
    by_subject = {item.subject_id: item.data_class for item in declarations}
    for subject_id in sorted(by_subject):
        require_subject_plane(connection, subject_id=subject_id, data_class=by_subject[subject_id])


def _insert_declaration(
    connection: Connection[Row],
    declaration: BootstrapDeclaration,
    *,
    ignore_conflict: bool,
) -> int:
    _insert_bootstrap_source(connection, declaration)
    conflict = "ON CONFLICT (record_id) DO NOTHING" if ignore_conflict else ""
    cursor = connection.execute(
        f"""
        INSERT INTO ynoy.bootstrap_declarations (
            record_id, source_record_id, subject_id, kind, statement, scope, decision_label,
            source_name, data_class, synthetic, status, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        {conflict}
        """,
        _declaration_values(declaration),
    )
    return cursor.rowcount


def _insert_bootstrap_source(
    connection: Connection[Row], declaration: BootstrapDeclaration
) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.bootstrap_sources
            (record_id, source_name, data_class, synthetic, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (record_id) DO NOTHING
        """,
        (
            declaration.source_record_id,
            declaration.source_name,
            declaration.data_class.value,
            declaration.synthetic,
            declaration.created_at,
        ),
    )


def _declaration_values(declaration: BootstrapDeclaration) -> tuple[object, ...]:
    return (
        declaration.record_id,
        declaration.source_record_id,
        declaration.subject_id,
        declaration.kind.value,
        declaration.statement,
        Jsonb(declaration.scope.model_dump(mode="json")),
        declaration.decision_label.value if declaration.decision_label else None,
        declaration.source_name,
        declaration.data_class.value,
        declaration.synthetic,
        declaration.status.value,
        declaration.created_at,
    )


def _candidate_values(candidate: ClaimCandidate) -> tuple[object, ...]:
    return (
        candidate.record_id,
        candidate.subject_id,
        candidate.claim_holder.value,
        candidate.kind.value,
        candidate.proposition,
        Jsonb(candidate.scope.model_dump(mode="json")),
        candidate.confidence,
        candidate.status.value,
        candidate.valid_from,
        candidate.valid_until,
        list(candidate.origin_cluster_ids),
        candidate.revision_of,
        candidate.superseded_by,
        candidate.created_at,
    )


def _lock_memory_target(connection: Connection[Row], record_id: UUID) -> tuple[str, str, DataClass]:
    for table, data_class in (
        ("bootstrap_declarations", None),
        ("claim_candidates", DataClass.DERIVED_IDENTITY),
    ):
        row = connection.execute(
            f"SELECT subject_id, {('data_class' if data_class is None else "'D3'")} "
            f"AS data_class FROM ynoy.{table} WHERE record_id = %s FOR UPDATE",
            (record_id,),
        ).fetchone()
        if row is not None:
            return table, str(row["subject_id"]), DataClass(str(row["data_class"]))
    raise DataValidationError("memory_record_not_found", "The scoped memory record was not found.")


def _save_replacement(
    connection: Connection[Row],
    replacement: BootstrapDeclaration | None,
    subject_id: str,
    *,
    target_data_class: DataClass,
) -> UUID | None:
    if replacement is None:
        return None
    if replacement.subject_id != subject_id:
        raise DataValidationError(
            "replacement_scope_mismatch",
            "Replacement must belong to the same represented subject.",
        )
    if replacement.data_class != target_data_class:
        raise PolicyViolation(
            "replacement_data_class_mismatch",
            "A replacement must remain in the target record's identity plane.",
        )
    require_subject_plane(connection, subject_id=subject_id, data_class=replacement.data_class)
    _insert_declaration(connection, replacement, ignore_conflict=False)
    return replacement.record_id
