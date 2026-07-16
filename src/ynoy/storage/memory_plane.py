from __future__ import annotations

from psycopg import Connection

from ynoy.errors import PolicyViolation
from ynoy.models import DataClass
from ynoy.storage.database import Row


def require_subject_plane(
    connection: Connection[Row], *, subject_id: str, data_class: DataClass
) -> None:
    """Fail fast on contention and reject mixed identity subjects."""
    lock_row = connection.execute(
        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS acquired",
        (f"ynoy:identity-plane:{subject_id}",),
    ).fetchone()
    if not lock_row or not lock_row["acquired"]:
        raise PolicyViolation(
            "identity_subject_busy",
            "Identity subject is being updated; retry the complete operation.",
        )
    row = connection.execute(
        """
        SELECT
          EXISTS (
            SELECT 1 FROM ynoy.bootstrap_declarations
            WHERE subject_id = %s AND data_class = 'D0'
            UNION ALL
            SELECT 1 FROM ynoy.source_events
            WHERE scope ->> 'person_id' = %s AND data_class = 'D0'
          ) AS has_synthetic,
          EXISTS (
            SELECT 1 FROM ynoy.bootstrap_declarations
            WHERE subject_id = %s AND data_class <> 'D0'
            UNION ALL
            SELECT 1 FROM ynoy.claim_candidates WHERE subject_id = %s
            UNION ALL
            SELECT 1 FROM ynoy.source_events
            WHERE scope ->> 'person_id' = %s AND data_class <> 'D0'
          ) AS has_private
        """,
        (subject_id, subject_id, subject_id, subject_id, subject_id),
    ).fetchone()
    has_synthetic = bool(row and row["has_synthetic"])
    has_private = bool(row and row["has_private"])
    if data_class == DataClass.PUBLIC_SYNTHETIC and has_private:
        raise PolicyViolation(
            "synthetic_subject_contains_private_identity",
            "Synthetic identity data cannot enter a subject with private identity records.",
        )
    if data_class != DataClass.PUBLIC_SYNTHETIC and has_synthetic:
        raise PolicyViolation(
            "private_subject_contains_synthetic_identity",
            "Private identity data cannot enter a subject with synthetic identity records.",
        )
