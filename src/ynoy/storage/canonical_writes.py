from __future__ import annotations

from uuid import UUID, uuid5

from psycopg import Connection
from psycopg.types.json import Jsonb

from ynoy.errors import DataValidationError
from ynoy.models import (
    CanonicalClaim,
    CanonicalClaimAdmission,
    ClaimAdmissionReceipt,
    ClaimSourceLink,
)
from ynoy.storage.database import Row

_EDGE_NAMESPACE = UUID("316aa7b1-b901-581d-9ed1-23cf62e2f0ce")


def persist_admission(connection: Connection[Row], admission: CanonicalClaimAdmission) -> None:
    _lock_superseded_claim(connection, admission.claim)
    _insert_claim(connection, admission.claim)
    for link in admission.source_links:
        _insert_source_link(connection, link)
    _insert_admission_receipt(connection, admission.receipt)
    _insert_derivation_edges(connection, admission)
    _mark_superseded(connection, admission.claim)


def _lock_superseded_claim(connection: Connection[Row], claim: CanonicalClaim) -> None:
    if claim.supersedes_claim_id is None:
        return
    row = connection.execute(
        """
        SELECT subject_id, data_class, target_layer, status
        FROM ynoy.canonical_claims WHERE record_id = %s FOR UPDATE
        """,
        (claim.supersedes_claim_id,),
    ).fetchone()
    expected = (claim.subject_id, claim.data_class.value, claim.target_layer.value, "confirmed")
    actual = (
        None
        if row is None
        else (
            str(row["subject_id"]),
            str(row["data_class"]),
            str(row["target_layer"]),
            str(row["status"]),
        )
    )
    if actual != expected:
        raise DataValidationError(
            "canonical_supersession_invalid",
            "A replacement must supersede one active claim in the same subject, plane, and layer.",
        )


def _insert_claim(connection: Connection[Row], claim: CanonicalClaim) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.canonical_claims (
            record_id, subject_id, claim_holder, source_authority, explicit_user_adoption,
            claim_type, target_layer, literal_statement, interpretation,
            candidate_consequence, persona_kind, persona_stratum, scope, decision_label,
            status, data_class, synthetic, admission_receipt_id, source_link_ids,
            supersedes_claim_id, superseded_by, claim_sha256, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        _claim_values(claim),
    )


def _claim_values(claim: CanonicalClaim) -> tuple[object, ...]:
    return (
        claim.record_id,
        claim.subject_id,
        claim.claim_holder.value,
        claim.source_authority.value,
        claim.explicit_user_adoption,
        claim.claim_type.value,
        claim.target_layer.value,
        claim.literal_statement,
        claim.interpretation,
        claim.candidate_consequence,
        claim.persona_kind.value if claim.persona_kind else None,
        claim.persona_stratum.value if claim.persona_stratum else None,
        Jsonb(claim.scope.model_dump(mode="json")),
        claim.decision_label.value if claim.decision_label else None,
        claim.status.value,
        claim.data_class.value,
        claim.synthetic,
        claim.admission_receipt_id,
        list(claim.source_link_ids),
        claim.supersedes_claim_id,
        claim.superseded_by,
        claim.claim_sha256,
        claim.created_at,
    )


def _insert_source_link(connection: Connection[Row], link: ClaimSourceLink) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.claim_source_links (
            record_id, claim_id, source_receipt_id, subject_id, source_data_class,
            source_response_sha256, character_start, character_end, span_text_sha256,
            origin_cluster_id, link_sha256, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            link.record_id,
            link.claim_id,
            link.source_receipt_id,
            link.subject_id,
            link.source_data_class.value,
            link.source_response_sha256,
            link.character_start,
            link.character_end,
            link.span_text_sha256,
            link.origin_cluster_id,
            link.link_sha256,
            link.created_at,
        ),
    )


def _insert_admission_receipt(connection: Connection[Row], receipt: ClaimAdmissionReceipt) -> None:
    connection.execute(
        """
        INSERT INTO ynoy.claim_admission_receipts (
            record_id, claim_id, subject_id, actor, claim_holder, source_authority,
            explicit_adoption, adoption_action, adoption_receipt_id,
            adoption_receipt_sha256, review_sha256, reviewed_state_sha256, claim_sha256,
            source_link_ids, source_count, data_class, supersedes_claim_id,
            receipt_sha256, authority, automatic_core_promotion, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        _receipt_values(receipt),
    )


def _receipt_values(receipt: ClaimAdmissionReceipt) -> tuple[object, ...]:
    return (
        receipt.record_id,
        receipt.claim_id,
        receipt.subject_id,
        receipt.actor.value,
        receipt.claim_holder.value,
        receipt.source_authority.value,
        receipt.explicit_adoption,
        receipt.adoption_action.value,
        receipt.adoption_receipt_id,
        receipt.adoption_receipt_sha256,
        receipt.review_sha256,
        receipt.reviewed_state_sha256,
        receipt.claim_sha256,
        list(receipt.source_link_ids),
        receipt.source_count,
        receipt.data_class.value,
        receipt.supersedes_claim_id,
        receipt.receipt_sha256,
        receipt.authority,
        receipt.automatic_core_promotion,
        receipt.created_at,
    )


def _insert_derivation_edges(
    connection: Connection[Row], admission: CanonicalClaimAdmission
) -> None:
    dependencies = [
        (link.source_receipt_id, link.record_id, link.origin_cluster_id)
        for link in admission.source_links
    ]
    dependencies += [
        (link.record_id, admission.claim.record_id, link.origin_cluster_id)
        for link in admission.source_links
    ]
    dependencies += [
        (link.record_id, admission.receipt.record_id, link.origin_cluster_id)
        for link in admission.source_links
    ]
    dependencies += [
        (
            admission.receipt.adoption_receipt_id,
            admission.receipt.record_id,
            admission.source_links[0].origin_cluster_id,
        ),
        (
            admission.receipt.record_id,
            admission.claim.record_id,
            admission.source_links[0].origin_cluster_id,
        ),
    ]
    for source_id, derived_id, cluster in dependencies:
        edge_id = uuid5(_EDGE_NAMESPACE, f"{source_id}:{derived_id}:derived_from")
        connection.execute(
            """
            INSERT INTO ynoy.derivation_edges (
                record_id, source_record_id, derived_record_id, relation,
                origin_cluster_id, created_at
            ) VALUES (%s, %s, %s, 'derived_from', %s, %s)
            """,
            (edge_id, source_id, derived_id, cluster, admission.claim.created_at),
        )


def _mark_superseded(connection: Connection[Row], claim: CanonicalClaim) -> None:
    if claim.supersedes_claim_id is not None:
        connection.execute(
            """
            UPDATE ynoy.canonical_claims
            SET status = 'superseded', superseded_by = %s
            WHERE record_id = %s
            """,
            (claim.record_id, claim.supersedes_claim_id),
        )
