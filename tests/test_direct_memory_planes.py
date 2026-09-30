from __future__ import annotations

import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest

from tests.direct_memory_fixtures import (
    NOW,
    PROJECT,
    SOURCE_ID,
    SOURCE_TEXT,
    make_native_review,
)
from ynoy.cli import main
from ynoy.direct_memory import DirectMemoryStore, FactProposal
from ynoy.direct_memory.codec import strict_dumps
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.errors import DataValidationError
from ynoy.extractor import LocalAtomicExtractor
from ynoy.reasoner import LocalOpenAIReasoner
from ynoy.util import sha256_text


def _write(root: Path, name: str, value: object) -> str:
    path = root / f"{name}.json"
    path.write_text(strict_dumps(value), encoding="utf-8")
    return str(path)


def _cli(
    root: Path,
    capsys: pytest.CaptureFixture[str],
    *arguments: str,
    synthetic: bool,
    expected: int = 0,
) -> object:
    command = ["--private-root", str(root), "direct-memory"]
    if synthetic:
        command.append("--synthetic")
    command.extend(arguments)
    code = main(command)
    output = json.loads(capsys.readouterr().out)
    assert code == expected, output
    assert output["ok"] == (expected == 0)
    return output.get("result", output.get("error"))


def _block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("direct-memory planes test attempted external work")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    monkeypatch.setattr(LocalOpenAIReasoner, "complete", forbidden)
    monkeypatch.setattr(LocalAtomicExtractor, "propose", forbidden)


def test_real_cli_cannot_read_synthetic_live_input_from_same_private_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_external_calls(monkeypatch)
    source_id = "synthetic-only-source"
    source_text = "Synthetic fixture says to keep answers concise."
    source_path = _write(
        tmp_path,
        "synthetic-live-input",
        {
            "source_id": source_id,
            "project": PROJECT,
            "said_at": NOW,
            "exact_text": source_text,
        },
    )
    recorded = _cli(
        tmp_path,
        capsys,
        "live-input",
        source_path,
        "--expected-revision",
        "0",
        synthetic=True,
    )
    assert recorded["source_id"] == source_id
    assert recorded["data_plane"] == DataPlane.PUBLIC_SYNTHETIC.value

    revision = _cli(tmp_path, capsys, "revision", PROJECT, synthetic=False)
    source = _cli(tmp_path, capsys, "source", source_id, synthetic=False, expected=2)
    cutoff = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    brief = _cli(
        tmp_path,
        capsys,
        "brief",
        PROJECT,
        "--as-of",
        cutoff,
        "--known-at",
        cutoff,
        synthetic=False,
    )

    assert revision["revision"] == 0
    assert source["code"] == "direct_memory_source_missing"
    assert brief["source_events"] == []
    assert (tmp_path / "direct-memory.sqlite3").is_file()
    assert (tmp_path / "direct-memory-synthetic.sqlite3").is_file()


def test_synthetic_cli_cannot_read_private_live_input_from_same_private_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_external_calls(monkeypatch)
    source_id = "private-only-source"
    source_path = _write(
        tmp_path,
        "private-live-input",
        {
            "source_id": source_id,
            "project": PROJECT,
            "said_at": NOW,
            "exact_text": "Private input remains in the private plane.",
        },
    )
    recorded = _cli(
        tmp_path,
        capsys,
        "live-input",
        source_path,
        "--expected-revision",
        "0",
        synthetic=False,
    )
    assert recorded["data_plane"] == DataPlane.PRIVATE.value

    revision = _cli(tmp_path, capsys, "revision", PROJECT, synthetic=True)
    source = _cli(tmp_path, capsys, "source", source_id, synthetic=True, expected=2)
    cutoff = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    brief = _cli(
        tmp_path,
        capsys,
        "brief",
        PROJECT,
        "--as-of",
        cutoff,
        "--known-at",
        cutoff,
        synthetic=True,
    )
    assert revision["revision"] == 0
    assert source["code"] == "direct_memory_source_missing"
    assert brief["source_events"] == []
    assert (tmp_path / "direct-memory.sqlite3").is_file()
    assert (tmp_path / "direct-memory-synthetic.sqlite3").is_file()


def test_api_plane_identity_survives_backup_and_rejects_cross_plane_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.sqlite3"
    store = DirectMemoryStore(path, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    source = store.record_live_user_input(
        source_id="plane-source",
        project="plane-project",
        said_at=NOW,
        exact_text="Synthetic plane source.",
        expected_revision=0,
    )
    assert source.data_plane is DataPlane.PUBLIC_SYNTHETIC
    assert source.sha256 == sha256_text("Synthetic plane source.")
    cutoff = datetime.now(UTC) + timedelta(days=1)
    brief = store.brief("plane-project", as_of=cutoff, known_at=cutoff)
    assert brief.data_plane is DataPlane.PUBLIC_SYNTHETIC
    assert brief.source_events == (source,)
    export = [json.loads(line) for line in store.export_jsonl().splitlines()]
    assert {row["record_type"] for row in export} == {"live_input", "source_event"}
    assert all(row["data_plane"] == DataPlane.PUBLIC_SYNTHETIC.value for row in export)
    source_row = next(row for row in export if row["record_type"] == "source_event")
    assert source_row["record"]["data_plane"] == DataPlane.PUBLIC_SYNTHETIC.value

    backup = store.backup(tmp_path / "synthetic-backup.sqlite3")
    for candidate in (path, backup):
        with pytest.raises(DataValidationError) as blocked:
            DirectMemoryStore(candidate, data_plane=DataPlane.PRIVATE)
        assert getattr(blocked.value, "code", None) == "direct_memory_database_identity"
    reopened = DirectMemoryStore(backup, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    assert reopened.current_revision("plane-project") == 1
    assert reopened.get_source_event("plane-source") == source
    assert store.current_revision("plane-project") == 1


def test_private_and_synthetic_native_reviews_must_match_their_data_plane(
    tmp_path: Path,
) -> None:
    native = make_native_review()
    proposal = FactProposal(
        fact_key="communication.concise",
        evidence_ids=(SOURCE_ID,),
        proposal=native.claims[0],
    )
    accepted = DirectMemoryStore(
        tmp_path / "synthetic.sqlite3", data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    private = DirectMemoryStore(tmp_path / "private.sqlite3", data_plane=DataPlane.PRIVATE)
    for store in (accepted, private):
        store.record_live_user_input(
            source_id=SOURCE_ID,
            project=PROJECT,
            said_at=NOW,
            exact_text=SOURCE_TEXT,
            expected_revision=0,
        )

    stored = accepted.build_review(
        SOURCE_ID, native.source, (proposal,), expected_revision=1
    )
    assert stored.review.source.synthetic is True
    with pytest.raises(DataValidationError) as private_blocked:
        private.build_review(SOURCE_ID, native.source, (proposal,), expected_revision=1)
    assert private_blocked.value.code == "direct_memory_data_plane_mismatch"
    private_receipt = native.source.model_copy(update={"synthetic": False})
    with pytest.raises(DataValidationError) as synthetic_blocked:
        accepted.build_review(SOURCE_ID, private_receipt, (proposal,), expected_revision=1)
    assert synthetic_blocked.value.code == "direct_memory_data_plane_mismatch"
    assert private.current_revision(PROJECT) == 1
    assert accepted.current_revision(PROJECT) == 2
    private_rows = [json.loads(line) for line in private.export_jsonl().splitlines()]
    accepted_rows = [json.loads(line) for line in accepted.export_jsonl().splitlines()]
    assert [row["record_type"] for row in private_rows].count("review") == 0
    assert [row["record_type"] for row in accepted_rows].count("review") == 1
