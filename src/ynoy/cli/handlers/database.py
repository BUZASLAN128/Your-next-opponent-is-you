from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext


def handle_database(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    database = context.setup_database()
    if args.database_command == "migrate":
        return {"status": "migrated", **database.migrate()}
    return {"status": "ok", **database.status()}
