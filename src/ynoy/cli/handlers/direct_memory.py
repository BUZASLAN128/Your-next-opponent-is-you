from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.cli.direct_memory_files import cutoff, output_path
from ynoy.cli.handlers.direct_memory_index import handle_index
from ynoy.cli.handlers.direct_memory_reviews import handle_reviews
from ynoy.cli.handlers.direct_memory_sources import handle_sources
from ynoy.direct_memory import DirectMemoryStore
from ynoy.errors import StorageError
from ynoy.policy import require_private_root

_INDEX_COMMANDS = {"import-document", "list-documents", "tree", "read-nodes", "read-pages"}
_SOURCE_COMMANDS = {
    "source-event",
    "live-input",
    "tool-result",
    "authorize",
    "attribute-authorship",
}
_REVIEW_COMMANDS = {"review", "correct", "claim-revision"}


def handle_direct_memory(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    root = require_private_root(
        context.settings.require_private_root(), real_data=not bool(args.synthetic)
    ).root
    operation = args.direct_memory_command
    if operation in _INDEX_COMMANDS:
        return handle_index(args, context, root)
    store = DirectMemoryStore(root / "direct-memory.sqlite3")
    if operation in _SOURCE_COMMANDS:
        return handle_sources(args, context, store)
    if operation in _REVIEW_COMMANDS:
        return handle_reviews(args, context, store)
    if operation == "revision":
        return {"project": args.project, "revision": store.current_revision(args.project)}
    if operation == "source":
        return store.get_source_event(args.source_id).model_dump(mode="json")
    if operation == "brief":
        return store.brief(
            args.project, as_of=cutoff(args.as_of), known_at=cutoff(args.known_at)
        ).model_dump(mode="json")
    destination = output_path(args.output, context)
    if operation == "backup":
        return {"backup_path": str(store.backup(destination))}
    content = store.export_jsonl(project=args.project)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except OSError as exc:
        raise StorageError(
            "direct_memory_export_failed", "JSONL export could not be written."
        ) from exc
    return {"export_path": str(destination), "project": args.project}
