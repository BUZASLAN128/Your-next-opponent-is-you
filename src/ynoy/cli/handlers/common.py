from __future__ import annotations

import argparse
from typing import cast
from uuid import UUID

from ynoy.config import Settings
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import AuditReceipt, DataClass, ScopeRef
from ynoy.reasoner import (
    DeterministicReasoner,
    LocalOpenAIReasoner,
    MissingLocalReasoner,
    Reasoner,
)
from ynoy.storage import AuditRepository, Database


def require_matching_mode(*, requested_synthetic: bool, artifact_synthetic: bool) -> None:
    if requested_synthetic != artifact_synthetic:
        raise PolicyViolation(
            "synthetic_mode_mismatch",
            "The command's synthetic flag does not match the private artifact.",
        )


def reasoner_from_args(args: argparse.Namespace, settings: Settings) -> Reasoner:
    if args.reasoner == "deterministic":
        return DeterministicReasoner()
    if settings.local_reasoner_url:
        return LocalOpenAIReasoner(
            endpoint=settings.local_reasoner_url,
            model=settings.local_reasoner_model,
            is_local=settings.local_model_attested,
        )
    return MissingLocalReasoner()


def scope_from_args(args: argparse.Namespace) -> ScopeRef:
    return ScopeRef.model_validate(
        {
            "project": args.project,
            "role": args.role,
            "audience": args.audience,
            "risk": cast(str, args.risk),
        }
    )


def parse_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise DataValidationError("uuid_invalid", f"{field} must be a valid UUID.") from exc


def append_audit(
    database: Database,
    *,
    event_type: str,
    reason_code: str,
    input_ids: tuple[str, ...],
    data_classes: tuple[DataClass, ...],
    artifact_id: str | None = None,
) -> None:
    AuditRepository(database).append(
        build_audit_receipt(
            event_type=event_type,
            reason_code=reason_code,
            input_ids=input_ids,
            data_classes=data_classes,
            artifact_id=artifact_id,
        )
    )


def build_audit_receipt(
    *,
    event_type: str,
    reason_code: str,
    input_ids: tuple[str, ...],
    data_classes: tuple[DataClass, ...],
    artifact_id: str | None = None,
) -> AuditReceipt:
    return AuditReceipt.model_validate(
        {
            "event_type": event_type,
            "actor_class": "local_cli",
            "config_version": "1.0",
            "opaque_input_ids": input_ids,
            "input_count": len(input_ids),
            "data_classes": data_classes,
            "decision": "complete",
            "reason_code": reason_code,
            "artifact_id": artifact_id,
            "status": "success",
        }
    )
