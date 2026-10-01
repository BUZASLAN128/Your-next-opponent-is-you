from __future__ import annotations

import argparse
import os
from uuid import uuid4

from ynoy.cli.context import CommandContext
from ynoy.cli.direct_memory_files import cutoff, output_path
from ynoy.cli.handlers.direct_memory_index import handle_index
from ynoy.cli.handlers.direct_memory_reviews import handle_reviews
from ynoy.cli.handlers.direct_memory_sources import handle_sources
from ynoy.direct_memory import DirectMemoryStore
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.errors import DataValidationError, StorageError
from ynoy.policy import require_private_root
from ynoy.private_files import (
    create_private_parents,
    ensure_private_root,
    open_exclusive_private_utf8,
)

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
    root = ensure_private_root(context.settings.require_private_root())
    require_private_root(root, real_data=not bool(args.synthetic))
    plane = DataPlane.PUBLIC_SYNTHETIC if args.synthetic else DataPlane.PRIVATE
    operation = args.direct_memory_command
    if operation in _INDEX_COMMANDS:
        return handle_index(args, context, root)
    filename = "direct-memory-synthetic.sqlite3" if args.synthetic else "direct-memory.sqlite3"
    store = DirectMemoryStore(root / filename, data_plane=plane)
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
    stage = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    stage_created = False
    try:
        create_private_parents(destination.parent, private_root=root)
        stream = open_exclusive_private_utf8(stage, private_root=root)
        stage_created = True
        with stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(stage, destination)
        except FileExistsError as exc:
            raise DataValidationError(
                "direct_memory_output_exists", "Output must use a new destination."
            ) from exc
    except OSError as exc:
        raise StorageError(
            "direct_memory_export_failed", "JSONL export could not be written."
        ) from exc
    finally:
        if stage_created:
            stage.unlink(missing_ok=True)
    return {"export_path": str(destination), "project": args.project}
