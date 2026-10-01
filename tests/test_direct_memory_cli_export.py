from __future__ import annotations

import json
from pathlib import Path

import pytest

import ynoy.cli.handlers.direct_memory as direct_memory_handler
from ynoy.cli import main
from ynoy.direct_memory import DirectMemoryStore


def test_export_failure_does_not_leave_a_partial_file_at_the_final_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "private"
    root.mkdir()
    destination = root / "backup.jsonl"
    monkeypatch.setattr(DirectMemoryStore, "export_jsonl", lambda self, project=None: "complete\n")
    opener = direct_memory_handler.open_exclusive_private_utf8

    class PartialFailure:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __enter__(self):
            self.wrapped.__enter__()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return self.wrapped.__exit__(exc_type, exc_value, traceback)

        def write(self, value: str) -> int:
            self.wrapped.write(value[:4])
            self.wrapped.flush()
            raise OSError("simulated interrupted export")

    monkeypatch.setattr(
        direct_memory_handler,
        "open_exclusive_private_utf8",
        lambda path, *, private_root: PartialFailure(
            opener(path, private_root=private_root)
        ),
    )

    code = main(
        [
            "--private-root",
            str(root),
            "direct-memory",
            "--synthetic",
            "export",
            "--output",
            str(destination),
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["error"]["code"] == "direct_memory_export_failed"
    assert not destination.exists()
    assert list(root.glob(".*.tmp")) == []
