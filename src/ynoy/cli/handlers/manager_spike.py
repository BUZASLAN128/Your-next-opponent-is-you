from __future__ import annotations

import argparse
from uuid import UUID

from ynoy.cli.context import CommandContext
from ynoy.errors import DataValidationError
from ynoy.executive_spike import resume_synthetic_mission, start_synthetic_mission, trace_mission


def handle_manager_spike(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    """Run the only allowlisted D0 executive fixture; user workspaces are never accepted."""
    if not bool(args.synthetic):
        raise DataValidationError(
            "executive_synthetic_required", "This executive spike requires --synthetic."
        )
    private_root = context.settings.require_private_root()
    if args.manager_command == "spike-start":
        trace = start_synthetic_mission(private_root, str(args.mission), int(args.max_new_steps))
    else:
        mission_id = _mission_id(str(args.mission_id))
        if args.manager_command == "spike-resume":
            trace = resume_synthetic_mission(private_root, mission_id, int(args.max_new_steps))
        else:
            trace = trace_mission(private_root, mission_id)
    return trace.model_dump(mode="json")


def _mission_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise DataValidationError(
            "executive_mission_id_invalid", "Mission identifier is invalid."
        ) from exc
