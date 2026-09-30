from __future__ import annotations

import argparse

from pydantic import TypeAdapter, ValidationError

from ynoy.cli.context import CommandContext
from ynoy.cli.direct_memory_files import load_input, load_model
from ynoy.cli.direct_memory_inputs import ClaimInput
from ynoy.cli.handlers.common import require_matching_mode
from ynoy.direct_memory import DirectMemoryStore, FactProposal, UserAuthorizationReceipt
from ynoy.errors import DataValidationError
from ynoy.models import ClaimReviewDecision, InteractionReceipt


def handle_reviews(
    args: argparse.Namespace, context: CommandContext, store: DirectMemoryStore
) -> dict[str, object]:
    if args.direct_memory_command == "review":
        return _review(args, context, store)
    if args.direct_memory_command == "claim-revision":
        return _claim(args, context, store)
    return _correct(args, context, store)


def _review(
    args: argparse.Namespace, context: CommandContext, store: DirectMemoryStore
) -> dict[str, object]:
    receipt = load_model(_read(args.receipt, args, context), InteractionReceipt)
    require_matching_mode(requested_synthetic=args.synthetic, artifact_synthetic=receipt.synthetic)
    claims = _typed(_read(args.claims, args, context), TypeAdapter(tuple[FactProposal, ...]))
    return store.build_review(
        args.source_id, receipt, claims, expected_revision=args.expected_revision
    ).model_dump(mode="json")


def _claim(
    args: argparse.Namespace, context: CommandContext, store: DirectMemoryStore
) -> dict[str, object]:
    authorization = load_model(_read(args.authorization, args, context), UserAuthorizationReceipt)
    item = load_model(_read(args.input, args, context), ClaimInput)
    return store.append_claim_revision(
        project=item.project,
        fact_key=item.fact_key,
        evidence_ids=item.evidence_ids,
        state=item.state,
        payload=item.payload,
        event_time=item.event_time,
        tool_receipt_id=item.tool_receipt_id,
        subject_id=item.subject_id,
        authorization=authorization,
        expected_revision=args.expected_revision,
    ).model_dump(mode="json")


def _correct(
    args: argparse.Namespace, context: CommandContext, store: DirectMemoryStore
) -> dict[str, object]:
    authorization = load_model(_read(args.authorization, args, context), UserAuthorizationReceipt)
    decisions = _typed(
        _read(args.decisions, args, context), TypeAdapter(tuple[ClaimReviewDecision, ...])
    )
    supersessions = (
        _typed(_read(args.supersessions, args, context), TypeAdapter(dict[str, str]))
        if args.supersessions
        else None
    )
    stored = store.get_review(args.review_id)
    require_matching_mode(
        requested_synthetic=args.synthetic, artifact_synthetic=stored.review.source.synthetic
    )
    return store.apply_correction(
        args.review_id,
        decisions,
        authorization,
        expected_revision=args.expected_revision,
        operation=args.operation,
        supersessions=supersessions,
    ).model_dump(mode="json")


def _read(value: str, args: argparse.Namespace, context: CommandContext) -> object:
    return load_input(value, context, synthetic=bool(args.synthetic))


def _typed[T](value: object, adapter: TypeAdapter[T]) -> T:
    try:
        return adapter.validate_python(value)
    except ValidationError as exc:
        raise DataValidationError(
            "direct_memory_input_invalid", "Input failed typed validation."
        ) from exc
