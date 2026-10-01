from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest

from ynoy.direct_memory.codec import strict_dumps, strict_loads
from ynoy.direct_memory.data_plane import DataPlane
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.sources import SourceOperations
from ynoy.errors import DataValidationError
from ynoy.models import Speaker
from ynoy.util import sha256_text

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def _operations(path: Path) -> SourceOperations:
    return SourceOperations(
        DirectMemoryDatabase(path, data_plane=DataPlane.PUBLIC_SYNTHETIC), clock=lambda: NOW
    )


def _append(operations: SourceOperations, source_id: str = "synthetic", revision: int = 0):
    return operations.record_source_event(
        source_id=source_id,
        project="synthetic-db",
        speaker=Speaker.THIRD_PARTY,
        said_at=NOW - timedelta(days=50),
        exact_text="Exact source ✓\n  Keep whitespace.\n",
        expected_revision=revision,
    )


def test_exact_source_and_actual_recorded_time_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.sqlite3"
    operations = _operations(path)
    source = _append(operations)
    loaded = _operations(path).get_source_event(source.source_id)
    assert loaded == source
    assert source.exact_text == "Exact source ✓\n  Keep whitespace.\n"
    assert source.sha256 == sha256_text(source.exact_text)
    assert source.speaker == Speaker.THIRD_PARTY
    assert source.said_at == NOW - timedelta(days=50)
    assert source.recorded_at == NOW
    assert operations.current_revision("synthetic-db") == 1
    with pytest.raises(TypeError):
        operations.record_source_event(
            source_id="backdate",
            project="synthetic-db",
            speaker=Speaker.USER,
            said_at=NOW,
            exact_text="Synthetic",
            expected_revision=1,
            recorded_at=NOW - timedelta(days=99),  # type: ignore[call-arg]
        )


def test_foreign_database_is_rejected_without_changing_bytes(tmp_path: Path) -> None:
    path = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES('synthetic retained')")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DataValidationError) as blocked:
        DirectMemoryDatabase(path, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    assert blocked.value.code == "direct_memory_database_identity"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_missing_append_only_trigger_rejects_existing_schema(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.sqlite3"
    database = DirectMemoryDatabase(path, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    with database.connect() as connection:
        connection.execute("DROP TRIGGER immutable_source_events_update")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DataValidationError) as blocked:
        DirectMemoryDatabase(path, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    assert blocked.value.code == "direct_memory_database_identity"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_transaction_failure_rolls_back_payload_and_revision(tmp_path: Path) -> None:
    database = DirectMemoryDatabase(
        tmp_path / "synthetic.sqlite3", data_plane=DataPlane.PUBLIC_SYNTHETIC
    )
    with pytest.raises(DataValidationError):
        with database.mutation("synthetic-db", 0) as (connection, revision):
            connection.execute(
                "INSERT INTO source_events VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    "partial",
                    "synthetic-db",
                    "user",
                    None,
                    NOW.isoformat(),
                    "Synthetic",
                    sha256_text("Synthetic"),
                    "imported",
                    revision,
                ),
            )
            strict_dumps({"invalid": float("nan")})
    assert database.current_revision("synthetic-db") == 0
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_events").fetchone()[0] == 0


def test_append_only_triggers_preserve_original_source(tmp_path: Path) -> None:
    operations = _operations(tmp_path / "synthetic.sqlite3")
    source = _append(operations)
    for sql in (
        "UPDATE source_events SET exact_text='altered' WHERE source_id='synthetic'",
        "DELETE FROM source_events WHERE source_id='synthetic'",
    ):
        with operations.database.connect() as connection, pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql)
    assert operations.get_source_event(source.source_id) == source


def test_concurrent_stale_writers_admit_exactly_one_successor(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.sqlite3"
    DirectMemoryDatabase(path, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    barrier = Barrier(2)

    def write(source_id: str) -> str:
        operations = _operations(path)
        expected = operations.current_revision("synthetic-db")
        barrier.wait(timeout=10)
        try:
            _append(operations, source_id, expected)
            return "committed"
        except DataValidationError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, ("writer-a", "writer-b")))
    assert sorted(results) == ["committed", "direct_memory_stale_revision"]
    database = DirectMemoryDatabase(path, data_plane=DataPlane.PUBLIC_SYNTHETIC)
    assert database.current_revision("synthetic-db") == 1
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_events").fetchone()[0] == 1


def test_backup_reload_and_foreign_target_preservation(tmp_path: Path) -> None:
    operations = _operations(tmp_path / "synthetic.sqlite3")
    source = _append(operations)
    target = tmp_path / "backup.sqlite3"
    operations.database.backup(target)
    assert _operations(target).get_source_event(source.source_id) == source
    foreign = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(foreign) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
    before = foreign.read_bytes()
    with pytest.raises(DataValidationError):
        operations.database.backup(foreign)
    assert foreign.read_bytes() == before


@pytest.mark.parametrize("invalid", ['{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":1,"x":2}'])
def test_strict_json_rejects_nonfinite_and_ambiguous_records(invalid: str) -> None:
    with pytest.raises(DataValidationError):
        strict_loads(invalid)


def test_strict_json_roundtrip_preserves_text(tmp_path: Path) -> None:
    value = {"synthetic": "\n Exact ✓ ", "finite": 1.25, "nested": [None, False, 4]}
    assert strict_loads(strict_dumps(value)) == value
