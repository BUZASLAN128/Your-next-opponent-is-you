from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.cli.direct_memory_files import load_input, load_model
from ynoy.cli.direct_memory_inputs import ImportedInput, LiveInput, ToolInput
from ynoy.direct_memory import DirectMemoryStore, UserAuthorizationReceipt


def handle_sources(
    args: argparse.Namespace, context: CommandContext, store: DirectMemoryStore
) -> dict[str, object]:
    command = args.direct_memory_command
    if command == "authorize":
        return store.authorize_action(
            args.source_id,
            action=args.action,
            payload_sha256=args.payload_sha256,
            subject_id=args.subject_id,
            review_sha256=args.review_sha256,
        ).model_dump(mode="json")
    if command == "attribute-authorship":
        auth = load_model(
            load_input(args.authorization, context, synthetic=bool(args.synthetic)),
            UserAuthorizationReceipt,
        )
        revision = store.attribute_source_authorship(
            args.source_id, auth, expected_revision=args.expected_revision
        )
        return {"source_id": args.source_id, "revision": revision}
    value = load_input(args.input, context, synthetic=bool(args.synthetic))
    return _record(value, args, store)


def _record(value: object, args: argparse.Namespace, store: DirectMemoryStore) -> dict[str, object]:
    command = args.direct_memory_command
    if command == "tool-result":
        tool = load_model(value, ToolInput)
        return store.record_tool_result(
            source_id=tool.source_id,
            project=tool.project,
            tool_name=tool.tool_name,
            operation=tool.operation,
            inputs=tool.inputs,
            result=tool.result,
            expected_revision=args.expected_revision,
        ).model_dump(mode="json")
    if command == "live-input":
        live = load_model(value, LiveInput)
        return store.record_live_user_input(
            source_id=live.source_id,
            project=live.project,
            said_at=live.said_at,
            exact_text=live.exact_text,
            subject_id=live.subject_id,
            authorization_intent=live.authorization_intent,
            expected_revision=args.expected_revision,
        ).model_dump(mode="json")
    imported = load_model(value, ImportedInput)
    return store.record_source_event(
        source_id=imported.source_id,
        project=imported.project,
        speaker=imported.speaker,
        said_at=imported.said_at,
        exact_text=imported.exact_text,
        expected_revision=args.expected_revision,
    ).model_dump(mode="json")
