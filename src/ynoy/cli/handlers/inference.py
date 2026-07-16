from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import append_audit, reasoner_from_args, scope_from_args
from ynoy.core import advisor_suggest, mirror_predict
from ynoy.models import DataClass
from ynoy.storage import Database, MemoryRepository
from ynoy.task_input import validate_task


def handle_mirror(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    task = validate_task(args.task)
    synthetic = bool(args.synthetic)
    database = context.database(synthetic=synthetic)
    data_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
    memory = MemoryRepository(database, inference_data_class=data_class)
    if synthetic:
        memory.assert_synthetic_only()
    else:
        memory.assert_private_inference_ready()
    reasoner = reasoner_from_args(args, context.settings)
    result = mirror_predict(
        memory,
        task=task,
        scope=scope_from_args(args),
        reasoner=reasoner,
        task_data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.PRIVATE_TASK),
    )
    _audit_prediction(database, result.evidence_receipts, synthetic)
    return {
        "status": "predicted",
        "reasoner": reasoner.name,
        "local_only": reasoner.is_local,
        "transport": "loopback" if reasoner.name == "local_openai_compatible" else "in_process",
        **result.model_dump(mode="json"),
    }


def handle_advisor(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    task = validate_task(args.task)
    synthetic = bool(args.synthetic)
    database = context.database(synthetic=synthetic)
    data_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
    memory = MemoryRepository(database, inference_data_class=data_class)
    if synthetic:
        memory.assert_synthetic_only()
    else:
        memory.assert_private_inference_ready()
    reasoner = reasoner_from_args(args, context.settings)
    result = advisor_suggest(
        memory,
        task=task,
        scope=scope_from_args(args),
        reasoner=reasoner,
        task_data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.PRIVATE_TASK),
    )
    _audit_prediction(database, result.evidence_receipts, synthetic)
    return {
        "status": "suggested",
        "reasoner": reasoner.name,
        "local_only": reasoner.is_local,
        "transport": "loopback" if reasoner.name == "local_openai_compatible" else "in_process",
        **result.model_dump(mode="json"),
    }


def _audit_prediction(database: Database, receipts: tuple[str, ...], synthetic: bool) -> None:
    append_audit(
        database,
        event_type="report",
        reason_code="local_no_action_prediction",
        input_ids=receipts,
        data_classes=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY,),
    )
