from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.common import scope_from_args
from ynoy.manager import start_manager


def handle_manager(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    """Start the explicit no-database manager surface."""
    del context
    result = start_manager(task=args.task, scope=scope_from_args(args))
    return result.model_dump(mode="json")
