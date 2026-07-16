from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.persona import build_persona_preview
from ynoy.persona_source import load_adopted_persona_source
from ynoy.policy import assert_outside_git, require_private_source


def handle_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    """Build a non-persisting preview from explicit declarations."""
    synthetic = bool(args.synthetic)
    source = Path(args.source)
    if not synthetic:
        assert_outside_git(source)
        source = require_private_source(source, context.settings.require_private_root())
    declarations = load_adopted_persona_source(source, synthetic=synthetic)
    return build_persona_preview(declarations).model_dump(mode="json")
