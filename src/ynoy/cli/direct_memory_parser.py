from __future__ import annotations

import argparse


def add_direct_memory_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = commands.add_parser("direct-memory")
    parser.add_argument("--synthetic", action="store_true")
    subcommands = parser.add_subparsers(dest="direct_memory_command", required=True)
    _source_parsers(subcommands)
    _review_parsers(subcommands)
    _read_parsers(subcommands)
    _index_parsers(subcommands)


def _write(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--expected-revision", type=int, required=True)
    return parser


def _source_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for name in ("source-event", "live-input", "tool-result"):
        _write(commands.add_parser(name)).add_argument("input")
    attribute = _write(commands.add_parser("attribute-authorship"))
    attribute.add_argument("source_id")
    attribute.add_argument("--authorization", required=True)
    authorize = commands.add_parser("authorize")
    authorize.add_argument("source_id")
    authorize.add_argument(
        "--action",
        required=True,
        choices=("correct", "retract", "supersede", "source_authorship", "claim_revision"),
    )
    authorize.add_argument("--payload-sha256", required=True)
    authorize.add_argument("--subject-id", default="self")
    authorize.add_argument("--review-sha256")


def _review_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    review = _write(commands.add_parser("review"))
    review.add_argument("source_id")
    review.add_argument("--receipt", required=True)
    review.add_argument("--claims", required=True)
    correction = _write(commands.add_parser("correct"))
    correction.add_argument("review_id")
    correction.add_argument("--decisions", required=True)
    correction.add_argument("--authorization", required=True)
    correction.add_argument(
        "--operation", choices=("correct", "retract", "supersede"), default="correct"
    )
    correction.add_argument("--supersessions")
    claim = _write(commands.add_parser("claim-revision"))
    claim.add_argument("input")
    claim.add_argument("--authorization", required=True)


def _read_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    commands.add_parser("revision").add_argument("project")
    commands.add_parser("source").add_argument("source_id")
    brief = commands.add_parser("brief")
    brief.add_argument("project")
    brief.add_argument("--as-of", required=True)
    brief.add_argument("--known-at", required=True)
    export = commands.add_parser("export")
    export.add_argument("--project")
    export.add_argument("--output", required=True)
    commands.add_parser("backup").add_argument("--output", required=True)


def _index_parsers(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    commands.add_parser("import-document").add_argument("input")
    commands.add_parser("list-documents")
    commands.add_parser("tree").add_argument("document_id")
    nodes = commands.add_parser("read-nodes")
    nodes.add_argument("document_id")
    nodes.add_argument("node_ids", nargs="+")
    pages = commands.add_parser("read-pages")
    pages.add_argument("document_id")
    pages.add_argument("page_numbers", type=int, nargs="+")
