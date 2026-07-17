from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.bootstrap import load_bootstrap
from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import build_audit_receipt, parse_uuid
from ynoy.cli.handlers.memory_admission import admit_canonical_claim
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import (
    BootstrapDeclaration,
    CanonicalClaim,
    ClaimCandidate,
    DataClass,
)
from ynoy.policy import assert_outside_git
from ynoy.storage import (
    MemoryInspectionRepository,
    MemoryMutationRepository,
    MemoryRepository,
)
from ynoy.util import new_id


def handle_memory(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    handlers = {"inspect": _inspect, "correct": _correct, "admit": admit_canonical_claim}
    return handlers[args.memory_command](args, context)


def _inspect(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    database = context.database(synthetic=synthetic)
    data_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
    if synthetic:
        MemoryRepository(database, inference_data_class=data_class).assert_synthetic_only(
            subject_id=args.subject_id
        )
    repository = MemoryInspectionRepository(database, data_class=data_class)
    declarations = repository.inspect_bootstrap_declarations(
        subject_id=args.subject_id,
        include_inactive=bool(args.include_inactive),
    )
    candidates = repository.inspect_claim_candidates(
        subject_id=args.subject_id,
        include_inactive=bool(args.include_inactive),
    )
    canonical = repository.inspect_canonical_claims(
        subject_id=args.subject_id,
        include_inactive=bool(args.include_inactive),
    )
    include_content = bool(args.include_content)
    return {
        "status": "inspected",
        "content_included": include_content,
        "declarations": [_declaration_view(item, include_content) for item in declarations],
        "candidates": [_candidate_view(item, include_content) for item in candidates],
        "canonical_claims": [_canonical_view(item, include_content) for item in canonical],
        "automatic_core_promotion": False,
    }


def _declaration_view(item: BootstrapDeclaration, include_content: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "record_id": str(item.record_id),
        "source_record_id": str(item.source_record_id),
        "kind": item.kind.value,
        "status": item.status.value,
        "scope": item.scope.model_dump(mode="json"),
        "source_authority": (
            "synthetic_fixture_declaration" if item.synthetic else "legacy_unverified_declaration"
        ),
        "synthetic": item.synthetic,
    }
    if include_content:
        result["statement"] = item.statement
    return result


def _candidate_view(item: ClaimCandidate, include_content: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "record_id": str(item.record_id),
        "kind": item.kind.value,
        "status": item.status.value,
        "scope": item.scope.model_dump(mode="json"),
        "confidence": item.confidence,
        "claim_holder": item.claim_holder.value,
        "origin_cluster_count": len(item.origin_cluster_ids),
    }
    if include_content:
        result["proposition"] = item.proposition
    return result


def _canonical_view(item: CanonicalClaim, include_content: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "record_id": str(item.record_id),
        "admission_receipt_id": str(item.admission_receipt_id),
        "claim_type": item.claim_type.value,
        "target_layer": item.target_layer.value,
        "status": item.status.value,
        "scope": item.scope.model_dump(mode="json"),
        "source_count": len(item.source_link_ids),
        "data_class": item.data_class.value,
    }
    if include_content:
        result["literal_statement"] = item.literal_statement
        result["interpretation"] = item.interpretation
    return result


def _correct(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    replacement = _load_replacement(args.replacement, synthetic)
    database = context.database(synthetic=synthetic)
    if synthetic:
        MemoryRepository(
            database, inference_data_class=DataClass.PUBLIC_SYNTHETIC
        ).assert_synthetic_only(subject_id=args.subject_id)
    target_id = parse_uuid(args.record_id, "record_id")
    audit = build_audit_receipt(
        event_type="derive",
        reason_code="represented_user_memory_correction",
        input_ids=(args.record_id,),
        data_classes=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY,),
        artifact_id=str(replacement.record_id) if replacement else None,
    )
    result = MemoryMutationRepository(database).correct(
        target_record_id=target_id,
        reason=args.reason.strip(),
        audit_receipt=audit,
        replacement=replacement,
        subject_id=args.subject_id,
    )
    return {"status": "corrected", **result}


def _load_replacement(value: str | None, synthetic: bool) -> BootstrapDeclaration | None:
    if value is None:
        return None
    source = Path(value)
    if not synthetic:
        assert_outside_git(source)
        raise PolicyViolation(
            "real_identity_persistence_unsupported",
            "Real replacement declarations require a provenance-preserving schema.",
        )
    replacements = load_bootstrap(source, synthetic=synthetic)
    if len(replacements) != 1:
        raise DataValidationError(
            "single_replacement_required",
            "Replacement source must contain exactly one declaration.",
        )
    return replacements[0].model_copy(update={"record_id": new_id()})
