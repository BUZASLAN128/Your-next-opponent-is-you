from __future__ import annotations

from pathlib import Path

import pytest

from tests.direct_memory_fixtures import NOW, PROJECT
from tests.test_direct_memory_temporal import _append_authorized_revision
from ynoy.direct_memory import DirectMemoryStore, ProvenanceState, json_bounds
from ynoy.direct_memory.codec import strict_dumps, strict_loads
from ynoy.errors import DataValidationError


@pytest.mark.parametrize("depth", [129, 1200, 10000])
def test_json_nesting_is_rejected_before_decoding(depth: int) -> None:
    with pytest.raises(DataValidationError) as rejected:
        strict_loads("[" * depth + "0" + "]" * depth)
    assert rejected.value.code == "direct_memory_json_invalid"


def test_json_depth_boundary_and_quoted_brackets_roundtrip() -> None:
    value = "[" * json_bounds.MAX_JSON_DEPTH + "0" + "]" * json_bounds.MAX_JSON_DEPTH
    assert strict_dumps(strict_loads(value)) == value
    quoted = {"synthetic": '"\\[{}]"' * 1000}
    assert strict_loads(strict_dumps(quoted)) == quoted


def test_json_item_inventory_has_explicit_neighbor_limit() -> None:
    value = "[" + ",".join("0" for _ in range(json_bounds.MAX_JSON_ITEMS)) + "]"
    assert len(strict_loads(value)) == json_bounds.MAX_JSON_ITEMS
    with pytest.raises(DataValidationError):
        strict_loads(value[:-1] + ",0]")


def test_json_byte_budget_counts_utf8_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(json_bounds, "MAX_JSON_BYTES", 6)
    assert strict_loads('"✓"') == "✓"
    with pytest.raises(DataValidationError):
        strict_loads('"✓✓"')
    with pytest.raises(DataValidationError):
        strict_dumps("✓✓")


@pytest.mark.parametrize("invalid", ['"\ud800"', '{"a":1,"a":2}', '{"a":1e999}'])
def test_malformed_unicode_duplicate_and_nonfinite_json_are_domain_errors(invalid: str) -> None:
    with pytest.raises(DataValidationError):
        strict_loads(invalid)


def test_project_partition_rejects_second_subject_atomically(tmp_path: Path) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    store.record_live_user_input(
        source_id="first-subject",
        project=PROJECT,
        subject_id="self",
        said_at=NOW,
        exact_text="Synthetic first subject context.",
        expected_revision=0,
    )
    with pytest.raises(DataValidationError):
        store.record_live_user_input(
            source_id="other-subject",
            project=PROJECT,
            subject_id="other",
            said_at=NOW,
            exact_text="Synthetic independent subject context.",
            expected_revision=1,
        )
    assert store.current_revision(PROJECT) == 1
    with pytest.raises(DataValidationError):
        store.get_source_event("other-subject")
    store.record_live_user_input(
        source_id="other-subject",
        project="synthetic-other-partition",
        subject_id="other",
        said_at=NOW,
        exact_text="Synthetic independent subject context.",
        expected_revision=0,
    )
    assert [event.source_id for event in store.brief(
        PROJECT, as_of=NOW, known_at=NOW
    ).source_events] == ["first-subject"]


def test_interrupted_backup_has_no_final_file_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    connect = store.database.connect
    source = connect()

    class InterruptedConnection:
        def backup(self, target: object) -> None:
            raise OSError("Synthetic interrupted backup")

        def close(self) -> None:
            source.close()

    monkeypatch.setattr(store.database, "connect", lambda: InterruptedConnection())
    destination = tmp_path / "published.sqlite3"
    with pytest.raises(OSError):
        store.backup(destination)
    assert not destination.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["memory.sqlite3"]
    monkeypatch.setattr(store.database, "connect", connect)
    store.backup(destination)
    assert DirectMemoryStore(destination).current_revision(PROJECT) == 0


def test_backup_verification_failure_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3")

    def reject(path: Path) -> None:
        raise DataValidationError("synthetic_backup_invalid", "Synthetic verification failure.")

    monkeypatch.setattr(store.database, "_validate_file", reject)
    destination = tmp_path / "unpublished.sqlite3"
    with pytest.raises(DataValidationError):
        store.backup(destination)
    assert not destination.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["memory.sqlite3"]


@pytest.mark.parametrize("changed", [{"operation": "deploy"}, {"item": "synthetic-A"}])
def test_unrelated_tool_operation_or_item_cannot_verify_another_result(
    tmp_path: Path, changed: dict[str, object]
) -> None:
    store = DirectMemoryStore(tmp_path / "memory.sqlite3", clock=lambda: NOW)
    result = {"operation": "check", "item": "synthetic-B", "status": "succeeded"}
    tool = store.record_tool_result(
        source_id="synthetic-check-result", project=PROJECT, tool_name="synthetic-check",
        operation="check", inputs={"item": "synthetic-B"}, result=result, expected_revision=0,
    )
    with pytest.raises(DataValidationError) as rejected:
        _append_authorized_revision(
            store, 99, ProvenanceState.TOOL_VERIFIED, {**result, **changed},
            evidence_ids=(tool.tool_receipt_id,), tool_receipt_id=tool.tool_receipt_id,
        )
    assert rejected.value.code == "direct_memory_tool_result_mismatch"
    assert store.list_claim_revisions(PROJECT) == ()
    assert store.get_source_event(tool.tool_receipt_id).exact_text == strict_dumps(result)
    with store.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM authorization_uses").fetchone()[0] == 0
