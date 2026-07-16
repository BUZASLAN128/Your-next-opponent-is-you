from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers import (
    handle_advisor,
    handle_benchmark,
    handle_bootstrap,
    handle_corpus,
    handle_database,
    handle_doctor,
    handle_erase,
    handle_manager,
    handle_memory,
    handle_mirror,
    handle_persona,
    handle_review,
)
from ynoy.cli.parser import parse_args
from ynoy.config import Settings
from ynoy.errors import YnoyError
from ynoy.util import json_default, redact_mapping

Handler = Callable[[argparse.Namespace, CommandContext], dict[str, object]]
HANDLERS: dict[str, Handler] = {
    "doctor": handle_doctor,
    "database": handle_database,
    "corpus": handle_corpus,
    "bootstrap": handle_bootstrap,
    "mirror": handle_mirror,
    "advisor": handle_advisor,
    "manager": handle_manager,
    "persona": handle_persona,
    "benchmark": handle_benchmark,
    "memory": handle_memory,
    "erase": handle_erase,
    "review": handle_review,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_environment(
        private_root=Path(args.private_root) if args.private_root else None,
        database_url=args.database_url,
    )
    context = CommandContext(settings=settings, repository_root=_repository_root())
    try:
        result = HANDLERS[args.command](args, context)
    except YnoyError as exc:
        _emit(
            {
                "ok": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": redact_mapping(exc.details),
                },
            },
            args.indent,
        )
        return 2
    except Exception:
        print(
            "ynoy: unexpected internal failure; no sensitive details were emitted", file=sys.stderr
        )
        _emit(
            {
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": "Unexpected internal failure.",
                    "details": {},
                },
            },
            args.indent,
        )
        return 3
    _emit({"ok": True, "result": result}, args.indent)
    return 0


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _emit(value: object, indent: int) -> None:
    print(
        json.dumps(
            value,
            default=json_default,
            ensure_ascii=False,
            indent=None if indent == 0 else indent,
            sort_keys=True,
        )
    )
