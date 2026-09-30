from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from ynoy.direct_memory.json_bounds import check_json_bounds
from ynoy.direct_memory.models import ProvenanceState, RevisionKind
from ynoy.errors import DataValidationError
from ynoy.models import ClaimReviewDecision
from ynoy.util import canonical_sha256, json_default, sha256_text


def strict_dumps(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            default=json_default,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        check_json_bounds(encoded)
        return encoded
    except (TypeError, ValueError, RecursionError) as exc:
        raise DataValidationError(
            "direct_memory_json_invalid", "Direct-memory values must be strict JSON."
        ) from exc


def strict_loads(value: str) -> object:
    try:
        check_json_bounds(value)
        return json.loads(
            value,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise DataValidationError(
            "direct_memory_json_invalid", "Stored direct-memory JSON is invalid."
        ) from exc


def decision_payload_sha256(decisions: Sequence[ClaimReviewDecision]) -> str:
    return canonical_sha256([item.model_dump(mode="json") for item in decisions])


def correction_payload_sha256(
    decisions: Sequence[ClaimReviewDecision],
    *,
    operation: str,
    supersessions: Mapping[str, str] | None = None,
) -> str:
    decision_digest = decision_payload_sha256(decisions)
    if operation != "supersede":
        if supersessions:
            raise DataValidationError(
                "direct_memory_supersession_invalid",
                "Only supersession may include replacement fact keys.",
            )
        return decision_digest
    return canonical_sha256(
        {
            "operation": operation,
            "decisions_sha256": decision_digest,
            "supersessions": dict(sorted((supersessions or {}).items())),
        }
    )


def source_authorship_payload_sha256(source_id: str, source_sha256: str, subject_id: str) -> str:
    return canonical_sha256(
        {"source_id": source_id, "source_sha256": source_sha256, "subject_id": subject_id}
    )


def claim_revision_payload_sha256(
    *,
    fact_key: str,
    evidence_ids: Sequence[str],
    state: ProvenanceState,
    kind: RevisionKind,
    payload: Mapping[str, object],
    event_time: datetime | None,
    tool_receipt_id: str | None = None,
    related_fact_key: str | None = None,
) -> str:
    canonical = strict_loads(
        strict_dumps(
            {
                "fact_key": fact_key,
                "evidence_ids": list(evidence_ids),
                "state": state.value,
                "kind": kind.value,
                "payload": payload,
                "event_time": event_time,
                "tool_receipt_id": tool_receipt_id,
                "related_fact_key": related_fact_key,
            }
        )
    )
    return canonical_sha256(canonical)


def hash_json(value: object) -> str:
    return sha256_text(strict_dumps(value))


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value
