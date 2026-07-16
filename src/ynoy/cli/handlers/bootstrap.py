from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.bootstrap import load_bootstrap
from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import build_audit_receipt
from ynoy.errors import PolicyViolation
from ynoy.models import DataClass
from ynoy.policy import assert_outside_git
from ynoy.storage import MemoryMutationRepository


def handle_bootstrap(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source = Path(args.source)
    if not synthetic:
        assert_outside_git(source)
        raise PolicyViolation(
            "real_identity_persistence_unsupported",
            "Real declarations are preview-only until adoption provenance can be persisted.",
        )
    database = context.database(synthetic=synthetic)
    declarations = load_bootstrap(source, synthetic=synthetic)
    audit = build_audit_receipt(
        event_type="derive",
        reason_code="explicit_declaration_import_not_inference",
        input_ids=tuple(str(item.source_record_id) for item in declarations),
        data_classes=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY,),
    )
    inserted = MemoryMutationRepository(database).add_bootstrap_declarations(declarations, audit)
    return {
        "status": "imported",
        "declaration_count": len(declarations),
        "inserted_count": inserted,
        "idempotent_replay_count": len(declarations) - inserted,
        "source_record_id": str(declarations[0].source_record_id),
        "authority": "synthetic_fixture_declaration",
        "automatic_core_promotion": False,
    }
