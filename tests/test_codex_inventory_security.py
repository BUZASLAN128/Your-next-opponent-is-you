from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.corpus import CodexInventoryLimits, CodexMetadataAdapter
from ynoy.errors import DataValidationError
from ynoy.metadata_artifacts import PrivateMetadataInventoryStore

_MARKER = b"YNOY_SYNTHETIC_CODEX_FIXTURE_V1\n"
_FIRST_RECORD = b'{"type":"session_meta","payload":{}}\n'


def _root(tmp_path: Path, name: str = "source") -> Path:
    root = tmp_path / name
    (root / "sessions").mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(_MARKER)
    return root


def _name(*, day: int = 2, identity: int = 1) -> str:
    return f"rollout-2026-01-{day:02d}T03-04-05-{UUID(int=identity)}.jsonl"


def _path(root: Path, *, day: int = 2, identity: int = 1) -> Path:
    return root / "sessions" / "2026" / "01" / f"{day:02d}" / _name(day=day, identity=identity)


def _write(path: Path, content: bytes = _FIRST_RECORD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class _FirstLineOnly:
    def __init__(self, handle: object, calls: list[int]):
        self.handle = handle
        self.calls = calls

    def __enter__(self) -> _FirstLineOnly:
        return self

    def __exit__(self, *args: object) -> object:
        return self.handle.__exit__(*args)  # type: ignore[union-attr]

    def readline(self, size: int) -> bytes:
        assert not self.calls, "session stream attempted a second line read"
        self.calls.append(size)
        return self.handle.readline(size)  # type: ignore[union-attr,no-any-return]

    def read(self, *_args: object) -> bytes:
        raise AssertionError("session stream must use one bounded readline")


class _BoundedScandir:
    def __init__(self, handle: object, maximum_reads: int):
        self.handle = handle
        self.maximum_reads = maximum_reads
        self.calls = 0

    def __enter__(self) -> _BoundedScandir:
        return self

    def __exit__(self, *_args: object) -> None:
        self.handle.close()  # type: ignore[union-attr]

    def __iter__(self) -> _BoundedScandir:
        return self

    def __next__(self) -> object:
        if self.calls >= self.maximum_reads:
            raise AssertionError("entry budget must be enforced before full directory consumption")
        self.calls += 1
        return next(self.handle)  # type: ignore[arg-type]


def test_reader_uses_exactly_one_bounded_readline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    _write(_path(root), _FIRST_RECORD + b"SECOND_LINE_MUST_NOT_BE_READ\n")
    real_fdopen = os.fdopen
    calls: list[int] = []

    def guarded_fdopen(*args: object, **kwargs: object) -> _FirstLineOnly:
        handle = real_fdopen(*args, **kwargs)  # type: ignore[arg-type]
        return _FirstLineOnly(handle, calls)

    monkeypatch.setattr("ynoy.corpus.codex_reader.os.fdopen", guarded_fdopen)
    manifest = CodexMetadataAdapter().inventory(root, synthetic=True)

    assert calls == [CodexInventoryLimits().max_first_record_bytes + 1]
    assert "SECOND_LINE_MUST_NOT_BE_READ" not in manifest.model_dump_json()


def test_noncanonical_jsonl_is_counted_but_never_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    canonical = _write(_path(root))
    ignored = _write(canonical.with_name("credential-session.jsonl"), b"DO_NOT_OPEN")
    real_open = os.open
    opened: list[Path] = []

    def guarded_open(path: Path, *args: object, **kwargs: object) -> int:
        current = Path(path)
        opened.append(current)
        assert current != ignored
        return real_open(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("ynoy.corpus.codex_reader.os.open", guarded_open)
    manifest = CodexMetadataAdapter().inventory(root, synthetic=True)

    assert opened == [canonical]
    assert manifest.entry_count == 1 and manifest.ignored_noncanonical_file_count == 1


@pytest.mark.parametrize("directory", ["auth", "backups-2026"])
def test_noncanonical_directory_is_rejected_before_scandir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: str
) -> None:
    root = _root(tmp_path)
    blocked = root / "sessions" / directory
    _write(blocked / "secret.jsonl", b"DO_NOT_SCAN")
    real_scandir = os.scandir
    seen: list[Path] = []

    def guarded_scandir(path: Path) -> object:
        current = Path(path)
        seen.append(current)
        if current == blocked:
            raise AssertionError("noncanonical child directory was scanned")
        return real_scandir(path)

    monkeypatch.setattr("ynoy.corpus.codex_discovery.os.scandir", guarded_scandir)
    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter().inventory(root, synthetic=True)

    assert error.value.code == "codex_noncanonical_directory"
    assert blocked not in seen


def test_entry_limit_stops_iteration_before_unbounded_sorting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    for index in range(4):
        (root / "sessions" / f"entry-{index}.txt").write_text("synthetic")
    real_scandir = os.scandir
    bounded: _BoundedScandir | None = None

    def bounded_scandir(path: Path) -> object:
        nonlocal bounded
        stream = real_scandir(path)
        if Path(path) == root / "sessions":
            bounded = _BoundedScandir(stream, maximum_reads=3)
            return bounded
        return stream

    monkeypatch.setattr("ynoy.corpus.codex_discovery.os.scandir", bounded_scandir)
    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter(CodexInventoryLimits(max_entries=2)).inventory(root, synthetic=True)

    assert error.value.code == "codex_inventory_entry_limit"
    assert bounded is not None and bounded.calls == 3


def test_reader_detects_mutation_after_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    target = _write(_path(root))
    real_fstat = os.fstat
    mutated = False

    def mutating_fstat(descriptor: int) -> os.stat_result:
        nonlocal mutated
        result = real_fstat(descriptor)
        if not mutated:
            mutated = True
            with target.open("ab") as stream:
                stream.write(b" ")
        return result

    monkeypatch.setattr("ynoy.corpus.codex_reader.os.fstat", mutating_fstat)
    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter().inventory(root, synthetic=True)

    assert mutated and error.value.code == "codex_source_changed_during_inventory"


def test_inventory_enforces_file_and_depth_limits(tmp_path: Path) -> None:
    file_root = _root(tmp_path, "file-limit")
    _write(_path(file_root, identity=1))
    _write(_path(file_root, identity=2))
    with pytest.raises(DataValidationError) as file_error:
        CodexMetadataAdapter(CodexInventoryLimits(max_files=1)).inventory(file_root, synthetic=True)
    assert file_error.value.code == "codex_inventory_file_limit"

    depth_root = _root(tmp_path, "depth-limit")
    _write(_path(depth_root))
    with pytest.raises(DataValidationError) as depth_error:
        CodexMetadataAdapter(CodexInventoryLimits(max_depth=0)).inventory(
            depth_root, synthetic=True
        )
    assert depth_error.value.code == "codex_inventory_depth_limit"


def test_inventory_rejects_symlinks_when_platform_supports_them(tmp_path: Path) -> None:
    root = _root(tmp_path)
    target = _write(root / "outside.jsonl")
    link = _path(root)
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("creating symlinks is unavailable in this test environment")

    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter().inventory(root, synthetic=True)

    assert error.value.code == "codex_symlink_rejected"


def test_inventory_rejects_junction_before_scanning_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    junction = root / "sessions" / "2026"
    junction.mkdir()
    real_is_junction = Path.is_junction
    real_scandir = os.scandir

    def marked_junction(path: Path) -> bool:
        return path == junction or real_is_junction(path)

    def guarded_scandir(path: Path) -> object:
        if Path(path) == junction:
            raise AssertionError("junction child was scanned")
        return real_scandir(path)

    monkeypatch.setattr(Path, "is_junction", marked_junction)
    monkeypatch.setattr("ynoy.corpus.codex_discovery.os.scandir", guarded_scandir)
    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter().inventory(root, synthetic=True)

    assert error.value.code == "codex_symlink_rejected"


def test_reader_rejects_inode_swap_when_identity_is_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    target = _write(_path(root))
    replacement = _write(root / "replacement.tmp", _FIRST_RECORD + b"replacement")
    if target.stat().st_ino == replacement.stat().st_ino:
        pytest.skip("filesystem does not expose distinct file identities")
    real_open = os.open
    swapped = False

    def swapping_open(path: Path, *args: object, **kwargs: object) -> int:
        nonlocal swapped
        if Path(path) == target and not swapped:
            swapped = True
            os.replace(replacement, target)
        return real_open(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("ynoy.corpus.codex_reader.os.open", swapping_open)
    with pytest.raises(DataValidationError) as error:
        CodexMetadataAdapter().inventory(root, synthetic=True)

    assert swapped and error.value.code == "codex_link_swap_rejected"


def test_manifest_store_rejects_tampered_or_renamed_content_before_write(
    tmp_path: Path,
) -> None:
    source = _root(tmp_path)
    _write(_path(source))
    manifest = CodexMetadataAdapter().inventory(source, synthetic=True)
    store = PrivateMetadataInventoryStore(tmp_path / "private", synthetic=True)
    invalid = (
        manifest.model_copy(update={"manifest_sha256": "0" * 64}),
        manifest.model_copy(update={"record_id": UUID(int=99)}),
    )

    for candidate in invalid:
        with pytest.raises(DataValidationError) as error:
            store.write_manifest(candidate)
        assert error.value.code == "codex_manifest_digest_mismatch"
    assert not (store.root / "codex-metadata-inventory").exists()
