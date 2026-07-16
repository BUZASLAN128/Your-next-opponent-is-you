from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.cli.context import CommandContext
from ynoy.cli.main import main
from ynoy.corpus import CodexContentPilotLimits, CodexContentSampleAdapter
from ynoy.corpus.codex import SYNTHETIC_MARKER
from ynoy.corpus.codex_sample import CodexContentSample
from ynoy.errors import DataValidationError
from ynoy.models import ClaimHolder, SourceAuthority, Speaker


def _source_root(tmp_path: Path, name: str = "codex-pilot-source") -> Path:
    root = tmp_path / name
    (root / "sessions").mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(SYNTHETIC_MARKER)
    return root


def _rollout_path(root: Path, *, day: int = 2, identity: int = 1, archived: bool = False) -> Path:
    name = f"rollout-2026-01-{day:02d}T03-04-05-{UUID(int=identity)}.jsonl"
    if archived:
        return root / "archived_sessions" / name
    return root / "sessions" / "2026" / "01" / f"{day:02d}" / name


def _session_meta(
    thread_id: str = "synthetic-thread", parent_thread_id: str | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": thread_id,
        "title": "SYNTHETIC_PRIVATE_TITLE",
        "cwd": "C:/synthetic/private/cwd",
    }
    if parent_thread_id is not None:
        payload["parent_thread_id"] = parent_thread_id
    return {"type": "session_meta", "payload": payload}


def _response(role: str, text: str, *, part_type: str = "input_text") -> dict[str, object]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": part_type, "text": text}],
        },
    }


def _event(kind: str, text: str) -> dict[str, object]:
    return {"type": "event_msg", "payload": {"type": kind, "message": text}}


def _write_rollout(path: Path, records: list[Mapping[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(f"{json.dumps(record, separators=(',', ':'))}\n" for record in records)
    path.write_text(content, encoding="utf-8")
    return path


def _sample(root: Path, **limit_overrides: int) -> object:
    limits = CodexContentPilotLimits(**limit_overrides)
    return CodexContentSampleAdapter(limits).sample(root, synthetic=True)


def _mixed_dialogue_sample(tmp_path: Path) -> tuple[CodexContentSample, tuple[str, str, str]]:
    root = _source_root(tmp_path)
    raw_ids = (
        "raw-thread-id-must-not-survive",
        "raw-parent-id-must-not-survive",
        "raw-turn-id-must-not-survive",
    )
    records = [
        _session_meta(raw_ids[0], raw_ids[1]),
        {"type": "turn_context", "payload": {"turn_id": raw_ids[2]}},
        _response("user", "repeated dialogue"),
        _event("user_message", "repeated dialogue"),
        _response("assistant", "visible assistant", part_type="output_text"),
        _response("developer", "DEVELOPER_CONTROL_SECRET"),
        _response("system", "SYSTEM_CONTROL_SECRET"),
        _response("tool", "TOOL_CONTROL_SECRET"),
        _response("assistant", "REASONING_PART_SECRET", part_type="reasoning_text"),
        {"type": "response_item", "payload": {"type": "reasoning", "text": "REASONING"}},
        _event("agent_reasoning", "EVENT_REASONING_SECRET"),
    ]
    _write_rollout(_rollout_path(root), records)
    return CodexContentSampleAdapter().sample(root, synthetic=True), raw_ids


def _run_pilot_cli(
    root: Path, private_root: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[dict[str, object], str]:
    code = main(
        [
            "--indent",
            "0",
            "--private-root",
            str(private_root),
            "corpus",
            "codex-pilot",
            str(root),
            "--synthetic",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0 and captured.err == "" and payload["ok"] is True
    return payload, captured.out


def test_selection_is_bounded_deterministic_and_covers_both_partitions(tmp_path: Path) -> None:
    root = _source_root(tmp_path)
    fixtures = (
        (2, 1, False, "session-small"),
        (3, 2, False, "session-selected-" + "s" * 80),
        (4, 3, True, "archive-small"),
        (5, 4, True, "archive-selected-" + "a" * 100),
    )
    for day, identity, archived, text in fixtures:
        _write_rollout(
            _rollout_path(root, day=day, identity=identity, archived=archived),
            [_session_meta(f"thread-{identity}"), _response("user", text)],
        )

    first = _sample(root, max_files=2)
    second = _sample(root, max_files=2)

    assert first.summary.selected_file_count == 2
    assert first.summary.selected_partition_counts == {"archived_sessions": 1, "sessions": 1}
    assert first.summary.selected_input_bytes <= first.summary.max_total_input_bytes
    assert {event.content for event in first.events} == {
        "session-selected-" + "s" * 80,
        "archive-selected-" + "a" * 100,
    }
    assert first.summary.normalized_snapshot_sha256 == second.summary.normalized_snapshot_sha256
    assert [event.event_id for event in first.events] == [event.event_id for event in second.events]


def test_dialogue_attribution_exclusions_repeats_and_lineage_are_preserved(
    tmp_path: Path,
) -> None:
    sample, raw_ids = _mixed_dialogue_sample(tmp_path)
    user_events = [event for event in sample.events if event.speaker == Speaker.USER]
    assistant = next(event for event in sample.events if event.speaker == Speaker.ASSISTANT)

    assert len(sample.events) == 3 and len(user_events) == 2
    assert all(
        event.source_authority == SourceAuthority.USER_TURN_UNATTRIBUTED for event in user_events
    )
    assert all(event.claim_holder == ClaimHolder.UNKNOWN for event in user_events)
    assert assistant.source_authority == SourceAuthority.ASSISTANT_CONTEXT
    assert assistant.claim_holder == ClaimHolder.ASSISTANT
    assert [event.content for event in user_events] == ["repeated dialogue"] * 2
    assert user_events[0].event_id != user_events[1].event_id
    assert (
        user_events[0].metadata["repeat_cluster_key"]
        == user_events[1].metadata["repeat_cluster_key"]
    )
    assert sample.summary.repeated_content_cluster_count == 1
    assert sample.summary.source_kind_counts == {
        "event_message": 1,
        "response_item_message": 2,
    }

    serialized = json.dumps(
        [event.model_dump(mode="json") for event in sample.events], sort_keys=True
    )
    forbidden = (
        *raw_ids,
        "DEVELOPER_CONTROL_SECRET",
        "SYSTEM_CONTROL_SECRET",
        "TOOL_CONTROL_SECRET",
        "REASONING_PART_SECRET",
        "EVENT_REASONING_SECRET",
    )
    assert all(value not in serialized for value in forbidden)
    assert all(event.parent_event_id is None for event in sample.events)
    assert all(
        event.metadata["thread_lineage"] == "explicit_parent_thread" for event in sample.events
    )
    assert all(len(str(event.metadata["thread_parent_key"])) == 64 for event in sample.events)
    assert all(len(event.conversation_id) == 64 for event in sample.events)
    assert sample.summary.explicit_parent_thread_count == 1


@pytest.mark.parametrize(
    ("bad_line", "expected_code"),
    [
        (b"{invalid-json}\n", "codex_pilot_invalid_jsonl"),
        (
            json.dumps(_event("user_message", "x" * 512)).encode() + b"\n",
            "codex_pilot_line_limit",
        ),
    ],
    ids=["invalid-jsonl", "oversized-line"],
)
def test_invalid_or_oversized_jsonl_fails_closed(
    tmp_path: Path, bad_line: bytes, expected_code: str
) -> None:
    root = _source_root(tmp_path)
    path = _rollout_path(root)
    path.parent.mkdir(parents=True)
    first = json.dumps(_session_meta(), separators=(",", ":")).encode() + b"\n"
    path.write_bytes(first + bad_line)

    with pytest.raises(DataValidationError) as error:
        _sample(root, max_line_bytes=256)

    assert error.value.code == expected_code


def test_cli_emits_only_content_free_summary_and_uses_no_storage_or_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _source_root(tmp_path)
    filename = _rollout_path(root)
    raw_values = (
        "RAW_MESSAGE_MUST_NOT_APPEAR",
        "synthetic-thread",
        "SYNTHETIC_PRIVATE_TITLE",
        "C:/synthetic/private/cwd",
        filename.name,
    )
    _write_rollout(filename, [_session_meta(), _response("user", raw_values[0])])
    private_root = tmp_path / "private-output"

    def forbidden_call(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("database, artifact store, or model provider was called")

    monkeypatch.setattr(CommandContext, "database", forbidden_call)
    monkeypatch.setattr(CommandContext, "artifacts", forbidden_call)
    monkeypatch.setattr(CommandContext, "metadata_inventory_artifacts", forbidden_call)
    monkeypatch.setattr("ynoy.reasoner.LocalOpenAIReasoner.__init__", forbidden_call)
    monkeypatch.setattr("ynoy.reasoner.DeterministicReasoner.complete", forbidden_call)

    payload, stdout = _run_pilot_cli(root, private_root, capsys)

    assert payload["result"]["status"] == "content_sampled_ephemerally"
    assert all(value not in stdout for value in raw_values)
    summary = payload["result"]["summary"]
    assert summary["content_emitted"] is False
    assert summary["content_persisted"] is False
    assert summary["private_artifact_written"] is False
    assert summary["database_used"] is False and summary["model_provider_used"] is False
    assert private_root.is_dir() and list(private_root.rglob("*")) == []


def test_cli_sanitizes_untrusted_discriminator_values_in_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _source_root(tmp_path)
    sentinels = (
        "PRIVATE_SENTINEL_OUTER_TYPE",
        "PRIVATE_SENTINEL_PAYLOAD_TYPE",
        "PRIVATE_SENTINEL_CONTENT_PART_TYPE",
    )
    records = [
        _session_meta(),
        {"type": sentinels[0], "payload": {"type": "private-inner"}},
        {"type": "response_item", "payload": {"type": sentinels[1]}},
        _response("assistant", "private part text", part_type=sentinels[2]),
    ]
    _write_rollout(_rollout_path(root), records)

    payload, stdout = _run_pilot_cli(root, tmp_path / "private-output", capsys)
    summary = payload["result"]["summary"]

    assert all(value not in stdout for value in sentinels)
    assert summary["record_type_counts"]["other"] == 1
    assert summary["excluded_counts"]["record:other:other"] == 1
    assert summary["excluded_counts"]["record:response_item:other"] == 1
    assert summary["excluded_counts"]["content_part:other"] == 1
