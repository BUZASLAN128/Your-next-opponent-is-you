from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.cli.main import main
from ynoy.errors import StorageError
from ynoy.storage import Database

pytestmark = pytest.mark.integration

_MARKER = b"YNOY_SYNTHETIC_CODEX_FIXTURE_V1\n"


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    day = root / "sessions" / "2026" / "01" / "01"
    day.mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(_MARKER)
    name = f"rollout-2026-01-01T03-04-05-{UUID(int=1)}.jsonl"
    records = (
        {"type": "session_meta", "payload": {"id": "synthetic-session"}},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "synthetic private text"}],
            },
        },
    )
    (day / name).write_bytes(b"".join(json.dumps(item).encode() + b"\n" for item in records))
    return root


def _run(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    return result


def test_codex_inventory_approve_snapshot_status_cli_round_trip(
    test_database: Database,
    test_database_url: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot, status = _cli_snapshot_flow(test_database_url, tmp_path, capsys)

    assert snapshot["status"] == status["status"] == "complete"
    assert snapshot["expected_bytes"] == snapshot["vaulted_bytes"]
    assert snapshot["byte_reconciliation_percent"] == 100
    assert snapshot["private_content_emitted"] is False
    assert status["model_provider_used"] is False
    ingestion = _run(
        [
            "--private-root",
            str(tmp_path / "private"),
            "--database-url",
            test_database_url,
            "corpus",
            "codex-ingest",
            str(snapshot["snapshot_id"]),
            "--synthetic",
        ],
        capsys,
    )
    assert ingestion["normalized_events"] == 2
    assert ingestion["dialogue_events"] == 1
    assert ingestion["model_provider_used"] is False
    _assert_receipt_immutable(test_database, UUID(str(snapshot["snapshot_id"])))


def _cli_snapshot_flow(
    database_url: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> tuple[dict[str, object], dict[str, object]]:
    source = _source(tmp_path)
    private = tmp_path / "private"
    common = ["--private-root", str(private), "--database-url", database_url]
    inventory = _run([*common, "corpus", "codex-inventory", str(source), "--synthetic"], capsys)
    approval = _run(
        [
            *common,
            "corpus",
            "approve",
            str(inventory["manifest_id"]),
            "--codex",
            "--synthetic",
        ],
        capsys,
    )
    snapshot = _run(
        [
            *common,
            "corpus",
            "codex-snapshot",
            str(source),
            str(inventory["manifest_id"]),
            str(approval["approval_id"]),
            "--synthetic",
        ],
        capsys,
    )
    status = _run(
        [
            *common,
            "corpus",
            "status",
            str(snapshot["snapshot_id"]),
            "--synthetic",
        ],
        capsys,
    )

    return snapshot, status


def _assert_receipt_immutable(database: Database, snapshot_id: UUID) -> None:
    with pytest.raises(StorageError):
        with database.connect() as connection:
            row = connection.execute(
                """
                SELECT latest_receipt_id AS record_id FROM ynoy.corpus_snapshots
                WHERE snapshot_id = %s
                """,
                (snapshot_id,),
            ).fetchone()
            assert row is not None
            connection.execute(
                "UPDATE ynoy.corpus_snapshot_receipts SET record = record WHERE record_id = %s",
                (row["record_id"],),
            )
