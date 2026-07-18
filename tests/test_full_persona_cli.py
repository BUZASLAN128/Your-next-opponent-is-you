from __future__ import annotations

from pathlib import Path

from support.full_persona import prepared_full_persona_source

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.study_full_persona import (
    freeze_full_persona,
    full_persona_status,
    scan_full_persona,
)
from ynoy.cli.parser import parse_args
from ynoy.config import Settings


def test_full_persona_parser_exposes_freeze_scan_and_status_commands(tmp_path: Path) -> None:
    source = str(tmp_path / "codex")
    study_id = "a" * 64
    cases = (
        (["study", "freeze-full-persona", source, study_id, "--synthetic"], "freeze-full-persona"),
        (
            ["study", "scan-full-persona", source, study_id, "--max-input-bytes", "7"],
            "scan-full-persona",
        ),
        (["study", "full-persona-status", study_id, "--synthetic"], "full-persona-status"),
    )

    for argv, command in cases:
        parsed = parse_args(argv)
        assert parsed.command == "study"
        assert parsed.study_command == command


def test_full_persona_handlers_smoke_without_private_output(tmp_path: Path) -> None:
    source_root, private_root, prepared = prepared_full_persona_source(tmp_path)
    context = CommandContext(
        settings=Settings.from_environment(private_root=private_root),
        repository_root=tmp_path,
    )
    freeze_args = parse_args(
        [
            "study",
            "freeze-full-persona",
            str(source_root),
            prepared.manifest.study_id,
            "--synthetic",
        ]
    )

    frozen = freeze_full_persona(freeze_args, context)
    run_id = str(frozen["run_id"])
    scan_args = parse_args(
        [
            "study",
            "scan-full-persona",
            str(source_root),
            run_id,
            "--max-input-bytes",
            "1024",
            "--synthetic",
        ]
    )
    scanned = scan_full_persona(scan_args, context)
    status_args = parse_args(["study", "full-persona-status", run_id, "--synthetic"])
    status = full_persona_status(status_args, context)

    assert frozen["status"] == "full_persona_frozen"
    assert scanned["status"] == "full_persona_scanning"
    assert status["status"] == "full_persona_status"
    for result in (frozen, scanned, status):
        assert "private_root" not in result
        assert "source_root" not in result
