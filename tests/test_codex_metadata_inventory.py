from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.cli.context import CommandContext
from ynoy.cli.main import main
from ynoy.corpus import CodexInventoryLimits, CodexMetadataAdapter
from ynoy.corpus.codex import verify_codex_metadata_inventory
from ynoy.errors import DataValidationError
from ynoy.metadata_artifacts import PrivateMetadataInventoryStore
from ynoy.models import ScopeRef

_MARKER = b"YNOY_SYNTHETIC_CODEX_FIXTURE_V1\n"
_SESSION_ID = "00000000-0000-0000-0000-000000000003"
_CONTENT_MARKER = "PRIVATE_MESSAGE_MARKER_MUST_NOT_APPEAR"
_TITLE_MARKER = "PRIVATE_TITLE_MARKER_MUST_NOT_APPEAR"
_CWD_MARKER = "C:/private/device/path/must-not-appear"


def _source_root(tmp_path: Path, name: str = "codex-source") -> Path:
    root = tmp_path / name
    (root / "sessions").mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(_MARKER)
    return root


def _rollout_name(*, day: int = 2, identity: int = 1) -> str:
    return f"rollout-2026-01-{day:02d}T03-04-05-{UUID(int=identity)}.jsonl"


def _canonical_path(root: Path, *, day: int = 2, identity: int = 1, archived: bool = False) -> Path:
    name = _rollout_name(day=day, identity=identity)
    if archived:
        return root / "archived_sessions" / name
    return root / "sessions" / "2026" / "01" / f"{day:02d}" / name


def _session_bytes() -> bytes:
    first = {
        "type": "session_meta",
        "payload": {"id": _SESSION_ID, "title": _TITLE_MARKER, "cwd": _CWD_MARKER},
    }
    second = {"type": "response_item", "payload": {"content": _CONTENT_MARKER}}
    return f"{json.dumps(first)}\n{json.dumps(second)}\n".encode()


def _write_session(path: Path, content: bytes | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_session_bytes() if content is None else content)
    return path


def _run_cli(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    return result


def _inventory_args(out: Path, src: Path) -> list[str]:
    return ["--private-root", str(out), "corpus", "codex-inventory", str(src)]


def test_inventory_accepts_only_canonical_layout_and_copies_no_private_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _source_root(tmp_path)
    canonical = _write_session(_canonical_path(root))
    _write_session(_canonical_path(root, day=3, identity=2, archived=True))
    ignored = _write_session(canonical.with_name("not-a-rollout.jsonl"))
    _write_session(root / "backups" / "backup.jsonl")
    _write_session(root / "auth" / "credential.jsonl")
    seen: list[Path] = []
    real_scandir = os.scandir

    def guarded_scandir(path: Path) -> object:
        current = Path(path)
        seen.append(current)
        assert "backups" not in current.parts and "auth" not in current.parts
        return real_scandir(path)

    monkeypatch.setattr("ynoy.corpus.codex_discovery.os.scandir", guarded_scandir)
    manifest = CodexMetadataAdapter().inventory(root, synthetic=True)
    serialized = manifest.model_dump_json()
    verify_codex_metadata_inventory(manifest)

    assert manifest.partition_counts == {"archived_sessions": 1, "sessions": 1}
    assert manifest.ignored_noncanonical_file_count == 1
    assert {path.name for path in seen} >= {"sessions", "archived_sessions"}
    private_values = (canonical.name, ignored.name, _SESSION_ID, _CONTENT_MARKER, _TITLE_MARKER)
    assert all(value not in serialized for value in (*private_values, _CWD_MARKER))


@pytest.mark.parametrize("marker", [None, b"wrong\n"], ids=["missing", "not-exact"])
def test_synthetic_inventory_requires_exact_marker(tmp_path: Path, marker: bytes | None) -> None:
    root = tmp_path / "source"
    (root / "sessions").mkdir(parents=True)
    if marker is not None:
        (root / ".ynoy-synthetic-codex-fixture").write_bytes(marker)

    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter().inventory(root, synthetic=True)

    assert error.value.code == "synthetic_fixture_marker_required"


def test_metadata_snapshot_is_deterministic_for_fixed_metadata(tmp_path: Path) -> None:
    roots = [_source_root(tmp_path, name) for name in ("first", "second")]
    for root in roots:
        _write_session(_canonical_path(root))
        _write_session(_canonical_path(root, day=3, identity=2, archived=True))
    kwargs = {
        "synthetic": True,
        "record_id": UUID("00000000-0000-4000-8000-000000000001"),
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }

    first = CodexMetadataAdapter().inventory(roots[0], **kwargs)
    second = CodexMetadataAdapter().inventory(roots[1], **kwargs)

    assert first.metadata_snapshot_sha256 == second.metadata_snapshot_sha256
    assert first.manifest_sha256 == second.manifest_sha256


def test_first_record_states_are_bounded_and_content_free(tmp_path: Path) -> None:
    root = _source_root(tmp_path)
    _write_session(_canonical_path(root, identity=1), b"")
    _write_session(_canonical_path(root, identity=2), b"{\n" + _CONTENT_MARKER.encode())
    _write_session(_canonical_path(root, identity=3), b"x" * 17)

    manifest = CodexMetadataAdapter(CodexInventoryLimits(max_first_record_bytes=16)).inventory(
        root, synthetic=True
    )

    assert manifest.state_counts == {
        "empty": 1,
        "invalid_first_record": 1,
        "oversized_first_record": 1,
    }
    assert _CONTENT_MARKER not in manifest.model_dump_json()


def test_manifest_store_rejects_other_models_and_tampered_exact_manifest(tmp_path: Path) -> None:
    source = _source_root(tmp_path)
    _write_session(_canonical_path(source))
    manifest = CodexMetadataAdapter().inventory(source, synthetic=True)
    tampered = manifest.model_copy(update={"manifest_sha256": "0" * 64})
    store = PrivateMetadataInventoryStore(tmp_path / "private", synthetic=True)

    assert store.write_manifest(manifest).is_file()
    with pytest.raises(DataValidationError) as integrity_error:
        verify_codex_metadata_inventory(tampered)
    assert integrity_error.value.code == "codex_manifest_digest_mismatch"
    with pytest.raises(DataValidationError) as store_error:
        store.write_manifest(tampered)
    assert store_error.value.code == "codex_manifest_digest_mismatch"
    with pytest.raises(DataValidationError) as model_error:
        store.write_manifest(ScopeRef())  # type: ignore[arg-type]
    assert model_error.value.code == "metadata_inventory_model_required"


def test_real_output_inside_git_is_blocked_before_source_scan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source_root(tmp_path)
    _write_session(_canonical_path(source))
    calls: list[str] = []
    monkeypatch.setattr(
        CodexMetadataAdapter,
        "inventory",
        lambda *_args, **_kwargs: calls.append("scanned"),
    )

    code = main(_inventory_args(Path(__file__).resolve().parents[1], source))
    payload = json.loads(capsys.readouterr().out)

    assert code == 2 and payload["error"]["code"] == "private_root_inside_git"
    assert calls == []


def test_cli_writes_private_manifest_without_database_or_model_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source_root(tmp_path)
    _write_session(_canonical_path(source))
    private = tmp_path / "private"
    monkeypatch.delenv("YNOY_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        CommandContext,
        "database",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("database called")),
    )

    result = _run_cli(_inventory_args(private, source), capsys)
    manifest_path = Path(str(result["manifest_path"]))

    assert result["database_used"] is False and result["model_provider_used"] is False
    assert result["content_fields_copied"] is False and result["claims_derived"] == 0
    assert manifest_path.is_file() and manifest_path.is_relative_to(private.resolve())
    assert _CONTENT_MARKER not in manifest_path.read_text(encoding="utf-8")
