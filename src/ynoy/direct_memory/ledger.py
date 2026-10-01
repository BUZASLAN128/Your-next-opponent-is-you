from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import uuid4

from ynoy.direct_memory.codec import (
    claim_revision_payload_sha256,
    strict_dumps,
    strict_loads,
)
from ynoy.direct_memory.models import (
    ClaimRevision,
    ProvenanceState,
    RevisionKind,
    UserAuthorizationReceipt,
)
from ynoy.errors import DataValidationError


def append_revision_record(
    connection: sqlite3.Connection,
    *,
    project: str,
    fact_key: str,
    evidence_ids: Sequence[str],
    state: ProvenanceState,
    kind: RevisionKind,
    payload: Mapping[str, object],
    event_time: datetime | None,
    recorded_at: datetime,
    authorization: UserAuthorizationReceipt | None,
    tool_receipt_id: str | None,
    related_fact_key: str | None,
    revision: int,
    payload_json: str | None = None,
) -> ClaimRevision:
    snapshot_json, parsed_payload = _canonical_payload_snapshot(payload, payload_json)
    digest = claim_revision_payload_sha256(
        fact_key=fact_key,
        evidence_ids=evidence_ids,
        state=state,
        kind=kind,
        payload=parsed_payload,
        event_time=event_time,
        tool_receipt_id=tool_receipt_id,
        related_fact_key=related_fact_key,
    )
    revision_id = str(uuid4())
    item = ClaimRevision(
        revision_id=revision_id,
        project=project,
        fact_key=fact_key,
        evidence_ids=tuple(evidence_ids),
        state=state,
        kind=kind,
        payload={str(key): value for key, value in parsed_payload.items()},
        event_time=event_time,
        recorded_at=recorded_at,
        authorization=authorization,
        tool_receipt_id=tool_receipt_id,
        related_fact_key=related_fact_key,
        revision=revision,
    )
    _insert_revision(connection, item, digest, snapshot_json)
    return item


def _canonical_payload_snapshot(
    payload: Mapping[str, object], payload_json: str | None
) -> tuple[str, dict[str, object]]:
    snapshot_json = strict_dumps(payload) if payload_json is None else payload_json
    parsed = strict_loads(snapshot_json)
    if not isinstance(parsed, dict):
        raise DataValidationError(
            "direct_memory_json_invalid", "Claim revision payload must be a JSON object."
        )
    if strict_dumps(parsed) != snapshot_json or (
        payload_json is not None and strict_dumps(payload) != snapshot_json
    ):
        raise DataValidationError(
            "direct_memory_json_invalid", "Claim revision payload snapshot is not canonical."
        )
    return snapshot_json, parsed


def _insert_revision(
    connection: sqlite3.Connection, item: ClaimRevision, digest: str, payload_json: str
) -> None:
    connection.execute(
        "INSERT INTO claim_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            item.revision_id,
            item.project,
            item.fact_key,
            strict_dumps(list(item.evidence_ids)),
            item.state.value,
            item.kind.value,
            payload_json,
            item.event_time.isoformat() if item.event_time else None,
            item.recorded_at.isoformat(),
            strict_dumps(item.authorization.model_dump(mode="json"))
            if item.authorization
            else None,
            item.tool_receipt_id,
            item.related_fact_key,
            digest,
            item.revision,
        ),
    )


def load_claim_revisions(
    connection: sqlite3.Connection,
    *,
    project: str,
    known_at: datetime | None = None,
    as_of: datetime | None = None,
    revision_cutoff: int | None = None,
) -> tuple[ClaimRevision, ...]:
    for cutoff in (known_at, as_of):
        if cutoff is not None and cutoff.utcoffset() is None:
            raise DataValidationError(
                "direct_memory_cutoff_invalid", "Temporal cutoffs must be timezone-aware."
            )
    if revision_cutoff is not None and revision_cutoff < 0:
        raise DataValidationError(
            "direct_memory_revision_invalid", "Revision cutoff cannot be negative."
        )
    query = "SELECT * FROM claim_revisions WHERE project=?"
    parameters: tuple[object, ...] = (project,)
    if revision_cutoff is not None:
        query += " AND revision<=?"
        parameters = (project, revision_cutoff)
    rows = connection.execute(query + " ORDER BY revision", parameters).fetchall()
    values = tuple(_claim_revision_from_row(row) for row in rows)
    return tuple(
        item
        for item in values
        if (revision_cutoff is not None or known_at is None or item.recorded_at <= known_at)
        and (as_of is None or item.event_time is None or item.event_time <= as_of)
    )


def _claim_revision_from_row(row: sqlite3.Row) -> ClaimRevision:
    try:
        payload = strict_loads(row["payload_json"])
        evidence = strict_loads(row["evidence_ids_json"])
        authorization = (
            strict_loads(row["authorization_json"]) if row["authorization_json"] else None
        )
        value = {
            "revision_id": row["revision_id"],
            "project": row["project"],
            "fact_key": row["fact_key"],
            "evidence_ids": evidence,
            "state": row["state"],
            "kind": row["kind"],
            "payload": payload,
            "event_time": row["event_time"],
            "recorded_at": row["recorded_at"],
            "authorization": authorization,
            "tool_receipt_id": row["tool_receipt_id"],
            "related_fact_key": row["related_fact_key"],
            "revision": row["revision"],
        }
        item = ClaimRevision.model_validate(value)
        digest = claim_revision_payload_sha256(
            fact_key=item.fact_key,
            evidence_ids=item.evidence_ids,
            state=item.state,
            kind=item.kind,
            payload=item.payload,
            event_time=item.event_time,
            tool_receipt_id=item.tool_receipt_id,
            related_fact_key=item.related_fact_key,
        )
        if digest != row["payload_sha256"]:
            raise ValueError("claim revision digest mismatch")
        return item
    except Exception as exc:
        raise DataValidationError(
            "direct_memory_claim_revision_integrity", "Stored claim revision failed verification."
        ) from exc
