from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.doctor import run_doctor


def handle_doctor(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    _ = args
    return run_doctor(context.settings, repository_root=context.repository_root)
