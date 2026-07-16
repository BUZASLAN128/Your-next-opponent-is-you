from __future__ import annotations

import stat
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipInfo

import pytest
from conftest import synthetic_conversation

from ynoy.archive import ArchiveLimits, iter_json_object_array, open_validated_zip
from ynoy.corpus import ChatGPTZipAdapter
from ynoy.corpus.types import branch_membership
from ynoy.errors import DataValidationError
from ynoy.models import ClaimHolder, DataClass, SourceAuthority, Speaker


def test_streaming_json_handles_one_byte_chunks_and_utf8() -> None:
    raw = '[{"name":"kişilik"},{"nested":{"value":2}}]'.encode()
    parsed = list(iter_json_object_array(BytesIO(raw), chunk_size=1))
    assert parsed == [{"name": "kişilik"}, {"nested": {"value": 2}}]


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"not":"an-array"}', "json_array_required"),
        (b'[{"unfinished":true}', "json_truncated"),
        (b"[{}] trailing", "json_trailing_content"),
        (b'["not-an-object"]', "json_object_required"),
    ],
)
def test_streaming_json_rejects_invalid_top_level(raw: bytes, code: str) -> None:
    with pytest.raises(DataValidationError) as error:
        list(iter_json_object_array(BytesIO(raw), chunk_size=2))
    assert error.value.code == code


def test_streaming_json_enforces_per_item_limit() -> None:
    with pytest.raises(DataValidationError) as error:
        list(iter_json_object_array(BytesIO(b'[{"value":"123456"}]'), max_item_bytes=8))
    assert error.value.code == "json_item_limit"


def test_streaming_json_enforces_nesting_limit() -> None:
    nested = b'[{"level1":[{"level2":{"value":1}}]}]'
    with pytest.raises(DataValidationError) as error:
        list(iter_json_object_array(BytesIO(nested), max_nesting=2, chunk_size=1))
    assert error.value.code == "json_nesting_limit"


def linear_branch_mapping() -> dict[str, dict[str, object]]:
    return {
        "root": {"parent": None, "children": ["child"]},
        "child": {"parent": "root", "children": ["leaf"]},
        "leaf": {"parent": "child", "children": []},
    }


def test_branch_membership_enforces_node_budget_before_graph_walk() -> None:
    with pytest.raises(DataValidationError) as blocked:
        branch_membership(linear_branch_mapping(), max_nodes=2)
    assert blocked.value.code == "conversation_node_limit"
    assert blocked.value.details == {"limit": 2}


def test_branch_membership_enforces_depth_budget() -> None:
    with pytest.raises(DataValidationError) as blocked:
        branch_membership(linear_branch_mapping(), max_depth=2)
    assert blocked.value.code == "conversation_branch_depth_limit"
    assert blocked.value.details == {"limit": 2}


def test_branch_membership_enforces_total_membership_work_budget() -> None:
    with pytest.raises(DataValidationError) as blocked:
        branch_membership(linear_branch_mapping(), max_pairs=2)
    assert blocked.value.code == "conversation_branch_membership_limit"
    assert blocked.value.details == {"limit": 2}


def test_chatgpt_adapter_forwards_custom_item_byte_limit(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip()
    adapter = ChatGPTZipAdapter(ArchiveLimits(max_json_item_bytes=64))
    with pytest.raises(DataValidationError) as error:
        adapter.inventory(archive_path, synthetic=True)
    assert error.value.code == "json_item_limit"


def test_archive_rejects_traversal_member(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip(member_name="../conversations.json")
    with pytest.raises(DataValidationError) as error:
        open_validated_zip(str(archive_path), ArchiveLimits())
    assert error.value.code == "archive_path_unsafe"


def test_archive_rejects_symlink_member(make_chatgpt_zip) -> None:
    link = ZipInfo("unsafe-link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive_path = make_chatgpt_zip(extra_info=link, extra_content=b"conversations.json")
    with pytest.raises(DataValidationError) as error:
        open_validated_zip(str(archive_path), ArchiveLimits())
    assert error.value.code == "archive_link_rejected"


def test_archive_enforces_entry_count_and_member_size(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip()
    with pytest.raises(DataValidationError) as count_error:
        open_validated_zip(str(archive_path), ArchiveLimits(max_entries=1))
    assert count_error.value.code == "archive_entry_limit"
    with pytest.raises(DataValidationError) as size_error:
        open_validated_zip(str(archive_path), ArchiveLimits(max_entry_bytes=16))
    assert size_error.value.code == "archive_member_too_large"


def test_archive_enforces_total_uncompressed_size(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip()
    with pytest.raises(DataValidationError) as error:
        open_validated_zip(str(archive_path), ArchiveLimits(max_total_uncompressed_bytes=16))
    assert error.value.code == "archive_expansion_limit"


def test_archive_enforces_compression_ratio(make_chatgpt_zip) -> None:
    extra = ZipInfo("compressible.txt")
    extra.compress_type = ZIP_DEFLATED
    archive_path = make_chatgpt_zip(extra_info=extra, extra_content=b"0" * 20_000)
    with pytest.raises(DataValidationError) as error:
        open_validated_zip(str(archive_path), ArchiveLimits(max_compression_ratio=2.0))
    assert error.value.code == "archive_compression_ratio"


def test_source_size_gate_fails_before_hash_read(
    make_chatgpt_zip, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_path = make_chatgpt_zip()
    opened = False

    def fail_if_opened(*_: object, **__: object):
        nonlocal opened
        opened = True
        raise AssertionError("oversized source must not be opened")

    monkeypatch.setattr(Path, "open", fail_if_opened)
    limits = ArchiveLimits(max_source_bytes=archive_path.stat().st_size - 1)
    with pytest.raises(DataValidationError) as error:
        ChatGPTZipAdapter(limits).inventory(archive_path, synthetic=True)
    assert error.value.code == "archive_source_too_large"
    assert opened is False


def test_synthetic_inventory_requires_marker(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip(marker=False)
    with pytest.raises(DataValidationError) as error:
        ChatGPTZipAdapter().inventory(archive_path, synthetic=True)
    assert error.value.code == "synthetic_fixture_marker_required"


def test_inventory_and_normalization_preserve_speaker_and_branch(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip()
    adapter = ChatGPTZipAdapter()
    manifest = adapter.inventory(archive_path, synthetic=True)
    events = list(adapter.iter_events(archive_path, manifest=manifest, import_run_id=uuid4()))
    assert manifest.source_data_class == DataClass.PUBLIC_SYNTHETIC
    assert manifest.conversation_count == 1
    assert manifest.message_count == 3
    assert manifest.branch_count == 2
    assert manifest.speaker_counts == {"assistant": 2, "user": 1}
    assert len(events) == 3
    user = next(event for event in events if event.speaker == Speaker.USER)
    assistants = [event for event in events if event.speaker == Speaker.ASSISTANT]
    assert user.claim_holder == ClaimHolder.UNKNOWN
    assert user.source_authority == SourceAuthority.USER_TURN_UNATTRIBUTED
    assert user.metadata["claim_attribution_status"] == "unreviewed_span"
    assert user.metadata["branch_membership_count"] == 2
    assert all(event.claim_holder == ClaimHolder.ASSISTANT for event in assistants)
    assert all(event.source_authority == SourceAuthority.ASSISTANT_CONTEXT for event in assistants)
    assert all(event.metadata["imported_instruction_is_inert"] is True for event in events)
    assert len({event.branch_id for event in assistants}) == 2
    assert {event.parent_event_id for event in assistants} == {user.event_id}


def test_inventory_counts_excluded_non_text_parts(make_chatgpt_zip) -> None:
    conversation = synthetic_conversation()
    mapping = conversation["mapping"]
    assert isinstance(mapping, dict)
    user = mapping["user-root"]
    assert isinstance(user, dict)
    message = user["message"]
    assert isinstance(message, dict)
    content = message["content"]
    assert isinstance(content, dict)
    content["parts"] = ["safe text", {"asset_pointer": "ignored"}]
    archive_path = make_chatgpt_zip(conversations=[conversation])
    manifest = ChatGPTZipAdapter().inventory(archive_path, synthetic=True)
    assert manifest.excluded_content_part_count == 1


def test_inventory_rejects_missing_conversation_file(make_chatgpt_zip) -> None:
    archive_path = make_chatgpt_zip(member_name="other.json")
    with pytest.raises(DataValidationError) as error:
        ChatGPTZipAdapter().inventory(archive_path, synthetic=True)
    assert error.value.code == "chatgpt_conversations_missing"


def test_inventory_detects_archive_digest_change(make_chatgpt_zip, tmp_path: Path) -> None:
    archive_path = make_chatgpt_zip()
    adapter = ChatGPTZipAdapter()
    manifest = adapter.inventory(archive_path, synthetic=True)
    changed = tmp_path / "changed.zip"
    changed.write_bytes(archive_path.read_bytes() + b"trailing")
    with pytest.raises(DataValidationError) as error:
        list(adapter.iter_events(changed, manifest=manifest, import_run_id=uuid4()))
    assert error.value.code == "archive_digest_mismatch"
