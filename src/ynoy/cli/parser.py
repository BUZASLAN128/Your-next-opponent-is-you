from __future__ import annotations

import argparse
from collections.abc import Sequence

from ynoy.models import CandidateKind, DecisionLabel, PersonaStratum


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ynoy")
    parser.add_argument("--private-root", type=str)
    parser.add_argument("--database-url", type=str)
    parser.add_argument("--indent", type=int, default=2, choices=range(0, 9))
    commands = parser.add_subparsers(dest="command", required=True)
    _doctor_parser(commands)
    _database_parser(commands)
    _corpus_parser(commands)
    _bootstrap_parser(commands)
    _persona_parser(commands)
    _manager_parser(commands)
    _inference_parsers(commands)
    _benchmark_parser(commands)
    _memory_parser(commands)
    _erase_parser(commands)
    _review_parser(commands)
    _study_parser(commands)
    return parser


def _doctor_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    commands.add_parser("doctor")


def _database_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("database")
    subcommands = parser.add_subparsers(dest="database_command", required=True)
    subcommands.add_parser("migrate")
    subcommands.add_parser("status")


def _corpus_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("corpus")
    subcommands = parser.add_subparsers(dest="corpus_command", required=True)
    inventory = subcommands.add_parser("inventory")
    inventory.add_argument("archive")
    inventory.add_argument("--synthetic", action="store_true")
    inventory.add_argument("--markdown-report", action="store_true")
    codex_inventory = subcommands.add_parser("codex-inventory")
    codex_inventory.add_argument("codex_root")
    codex_inventory.add_argument("--synthetic", action="store_true")
    codex_pilot = subcommands.add_parser("codex-pilot")
    codex_pilot.add_argument("codex_root")
    codex_pilot.add_argument("--synthetic", action="store_true")
    approve = subcommands.add_parser("approve")
    approve.add_argument("manifest_id")
    approve.add_argument("--synthetic", action="store_true")
    approve.add_argument(
        "--operations",
        nargs="+",
        default=["ingest", "derive", "benchmark", "report"],
        choices=["ingest", "derive", "benchmark", "report"],
    )
    approve.add_argument("--retention-days", type=int)
    approve.add_argument("--third-party-reviewed", action="store_true")
    ingest = subcommands.add_parser("ingest")
    ingest.add_argument("archive")
    ingest.add_argument("manifest_id")
    ingest.add_argument("approval_id")
    ingest.add_argument("--synthetic", action="store_true")


def _bootstrap_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("bootstrap")
    subcommands = parser.add_subparsers(dest="bootstrap_command", required=True)
    import_parser = subcommands.add_parser("import")
    import_parser.add_argument("source")
    import_parser.add_argument("--synthetic", action="store_true")


def _persona_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("persona")
    subcommands = parser.add_subparsers(dest="persona_command", required=True)
    preview = subcommands.add_parser("preview")
    preview.add_argument("--subject-id", default="self")
    preview.add_argument("--synthetic", action="store_true")


def _inference_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    mirror = commands.add_parser("mirror")
    mirror_commands = mirror.add_subparsers(dest="mirror_command", required=True)
    _add_inference_arguments(mirror_commands.add_parser("predict"))
    advisor = commands.add_parser("advisor")
    advisor_commands = advisor.add_subparsers(dest="advisor_command", required=True)
    _add_inference_arguments(advisor_commands.add_parser("suggest"))


def _manager_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("manager")
    subcommands = parser.add_subparsers(dest="manager_command", required=True)
    start = subcommands.add_parser("start")
    start.add_argument("--task", required=True)
    _add_scope_arguments(start)


def _add_inference_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task", required=True)
    _add_scope_arguments(parser)
    parser.add_argument("--reasoner", choices=["local", "deterministic"], default="local")
    parser.add_argument("--synthetic", action="store_true")


def _add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project")
    parser.add_argument("--role")
    parser.add_argument("--audience")
    parser.add_argument("--risk", choices=["low", "medium", "high", "unknown"], default="unknown")


def _benchmark_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("benchmark")
    subcommands = parser.add_subparsers(dest="benchmark_command", required=True)
    freeze = subcommands.add_parser("freeze")
    freeze.add_argument("cases")
    freeze.add_argument("--name", required=True)
    freeze.add_argument("--development-fraction", type=float, default=0.7)
    run = subcommands.add_parser("run")
    run.add_argument("manifest_id")
    report = subcommands.add_parser("report")
    report.add_argument("manifest_id")
    report.add_argument("run_id")


def _memory_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("memory")
    subcommands = parser.add_subparsers(dest="memory_command", required=True)
    inspect = subcommands.add_parser("inspect")
    inspect.add_argument("--subject-id", default="self")
    inspect.add_argument("--include-inactive", action="store_true")
    inspect.add_argument("--include-content", action="store_true")
    inspect.add_argument("--synthetic", action="store_true")
    correct = subcommands.add_parser("correct")
    correct.add_argument("record_id")
    correct.add_argument("--reason", required=True)
    correct.add_argument("--replacement")
    correct.add_argument("--subject-id", default="self")
    correct.add_argument("--synthetic", action="store_true")
    admit = subcommands.add_parser("admit")
    admit.add_argument("review")
    admit.add_argument("--receipt", action="append", required=True)
    admit.add_argument("--claim-id", required=True)
    admit.add_argument("--supersedes-claim-id")
    admit.add_argument("--decision-label", choices=tuple(item.value for item in DecisionLabel))
    admit.add_argument("--persona-kind", choices=tuple(item.value for item in CandidateKind))
    admit.add_argument("--persona-stratum", choices=tuple(item.value for item in PersonaStratum))
    admit.add_argument("--synthetic", action="store_true")


def _erase_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("erase")
    subcommands = parser.add_subparsers(dest="erase_command", required=True)
    plan = subcommands.add_parser("plan")
    plan.add_argument("source_id")
    plan.add_argument("--synthetic", action="store_true")
    confirm = subcommands.add_parser("confirm")
    confirm.add_argument("plan_id")
    confirm.add_argument("plan_sha256")
    confirm.add_argument("--synthetic", action="store_true")


def _review_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("review")
    subcommands = parser.add_subparsers(dest="review_command", required=True)
    propose = subcommands.add_parser("propose")
    propose.add_argument("interaction")
    _add_review_data_arguments(propose)
    batch = subcommands.add_parser("batch")
    batch.add_argument("review")
    batch.add_argument("--start", type=int, default=1)
    batch.add_argument("--limit", type=int, default=5)
    _add_review_data_arguments(batch)
    apply = subcommands.add_parser("apply")
    apply.add_argument("review")
    apply.add_argument("decisions")
    apply.add_argument("--receipt", action="append", default=[])
    _add_review_data_arguments(apply)
    replay = subcommands.add_parser("replay")
    replay.add_argument("review")
    replay.add_argument("--receipt", action="append", default=[])
    _add_review_data_arguments(replay)


def _add_review_data_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--synthetic", action="store_true")


def _study_parser(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("study")
    subcommands = parser.add_subparsers(dest="study_command", required=True)
    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("codex_root")
    prepare.add_argument("--synthetic", action="store_true")
    status = subcommands.add_parser("status")
    status.add_argument("study_id")
    status.add_argument("--synthetic", action="store_true")
    purge = subcommands.add_parser("purge-expired")
    purge.add_argument("--synthetic", action="store_true")
    delete = subcommands.add_parser("delete")
    delete.add_argument("study_id")
    delete.add_argument("--synthetic", action="store_true")
    submit = subcommands.add_parser("submit-labels")
    submit.add_argument("study_id")
    submit.add_argument("--synthetic", action="store_true")
    seal = subcommands.add_parser("seal-labels")
    seal.add_argument("study_id")
    seal.add_argument("--synthetic", action="store_true")
    propose = subcommands.add_parser("propose-labels")
    propose.add_argument("study_id")
    propose.add_argument("--synthetic", action="store_true")
    propose.add_argument("--retry-unreliable", action="store_true")
    record_review = subcommands.add_parser("record-proposal-review")
    record_review.add_argument("study_id")
    record_review.add_argument("--synthetic", action="store_true")
    record_review.add_argument("--confirm")
    record_review.add_argument("--not-mine")
    record_review.add_argument("--correct")
    record_review.add_argument("--corrections-file")
    submit_review = subcommands.add_parser("submit-proposal-review")
    submit_review.add_argument("study_id")
    submit_review.add_argument("--synthetic", action="store_true")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)
