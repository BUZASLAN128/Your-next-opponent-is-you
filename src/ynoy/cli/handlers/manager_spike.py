from __future__ import annotations

import argparse
from uuid import UUID

from ynoy.cli.context import CommandContext
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.executive_spike import (
    compare_synthetic_planners,
    resume_synthetic_mission,
    start_synthetic_mission,
    trace_mission,
)
from ynoy.executive_spike.proposer import LocalExecutiveProposer


def handle_manager_spike(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    """Run the only allowlisted D0 executive fixture; user workspaces are never accepted."""
    if not bool(args.synthetic):
        raise DataValidationError(
            "executive_synthetic_required", "This executive spike requires --synthetic."
        )
    private_root = context.settings.require_private_root()
    if args.manager_command == "spike-start":
        trace = start_synthetic_mission(private_root, str(args.mission), int(args.max_new_steps))
    elif args.manager_command == "spike-compare":
        comparison = compare_synthetic_planners(
            private_root, str(args.mission), _configured_proposer(context)
        )
        return comparison.model_dump(mode="json")
    else:
        mission_id = _mission_id(str(args.mission_id))
        if args.manager_command == "spike-resume":
            trace = resume_synthetic_mission(private_root, mission_id, int(args.max_new_steps))
        else:
            trace = trace_mission(private_root, mission_id)
    return trace.model_dump(mode="json")


def _configured_proposer(context: CommandContext) -> LocalExecutiveProposer:
    settings = context.settings
    if not (
        settings.local_reasoner_url
        and settings.local_reasoner_model_explicit
        and settings.local_reasoner_revision
        and settings.local_reasoner_artifact_sha256
    ):
        raise PolicyViolation(
            "executive_model_not_configured",
            "Configure the attested loopback model, revision, and artifact SHA-256.",
        )
    return LocalExecutiveProposer(
        endpoint=settings.local_reasoner_url,
        model=settings.local_reasoner_model,
        revision=settings.local_reasoner_revision,
        artifact_sha256=settings.local_reasoner_artifact_sha256,
        local_attested=settings.local_model_attested,
    )


def _mission_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise DataValidationError(
            "executive_mission_id_invalid", "Mission identifier is invalid."
        ) from exc
