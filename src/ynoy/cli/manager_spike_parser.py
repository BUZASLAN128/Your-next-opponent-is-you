from __future__ import annotations

import argparse


def add_manager_spike_parsers(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the D0-only persistent executive-loop demonstration commands."""
    start = subcommands.add_parser("spike-start")
    start.add_argument("--mission", required=True)
    start.add_argument("--synthetic", action="store_true", required=True)
    start.add_argument("--max-new-steps", type=int, default=8)
    resume = subcommands.add_parser("spike-resume")
    resume.add_argument("mission_id")
    resume.add_argument("--synthetic", action="store_true", required=True)
    resume.add_argument("--max-new-steps", type=int, default=8)
    trace = subcommands.add_parser("spike-trace")
    trace.add_argument("mission_id")
    trace.add_argument("--synthetic", action="store_true", required=True)
    compare = subcommands.add_parser("spike-compare")
    compare.add_argument("--mission", required=True)
    compare.add_argument("--synthetic", action="store_true", required=True)
