from __future__ import annotations

import argparse


def add_full_persona_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    freeze = commands.add_parser("freeze-full-persona")
    freeze.add_argument("codex_root")
    freeze.add_argument("source_study_id")
    freeze.add_argument("--synthetic", action="store_true")
    scan = commands.add_parser("scan-full-persona")
    scan.add_argument("codex_root")
    scan.add_argument("run_id")
    scan.add_argument("--max-input-bytes", type=int)
    scan.add_argument("--synthetic", action="store_true")
    status = commands.add_parser("full-persona-status")
    status.add_argument("run_id")
    status.add_argument("--synthetic", action="store_true")
    delete = commands.add_parser("delete-full-persona")
    delete.add_argument("run_id")
    delete.add_argument("--synthetic", action="store_true")
    build_pack = commands.add_parser("build-full-persona-pack")
    build_pack.add_argument("run_id")
    build_pack.add_argument("--max-atoms-per-layer", type=int, default=128)
    build_pack.add_argument("--max-excerpt-chars", type=int, default=2048)
    build_pack.add_argument("--synthetic", action="store_true")
    query_pack = commands.add_parser("query-full-persona-pack")
    query_pack.add_argument("run_id")
    query_pack.add_argument("query")
    query_pack.add_argument("--top-k", type=int, default=5)
    query_pack.add_argument("--synthetic", action="store_true")
    profile = commands.add_parser("profile-full-persona")
    profile.add_argument("run_id")
    profile.add_argument("--synthetic", action="store_true")
    respond = commands.add_parser("respond-full-persona")
    respond.add_argument("run_id")
    respond.add_argument("query")
    respond.add_argument("--arm", choices=("structured", "generic"), default="structured")
    respond.add_argument("--synthetic", action="store_true")
