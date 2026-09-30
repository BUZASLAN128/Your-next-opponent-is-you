from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.private_files import (
    create_private_file,
    create_private_parents,
    ensure_private_root,
    open_exclusive_private_utf8,
    validate_private_file,
)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission modes are not Windows ACLs")
def test_new_private_directories_and_files_use_owner_only_modes(tmp_path: Path) -> None:
    previous_umask = os.umask(0o022)
    try:
        root = ensure_private_root(tmp_path / "private")
        nested = create_private_parents(root / "ledger" / "exports", private_root=root)
        target = nested / "events.jsonl"
        with open_exclusive_private_utf8(target, private_root=root) as stream:
            stream.write("synthetic ✓\n")

        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE((root / "ledger").stat().st_mode) == 0o700
        assert stat.S_IMODE(nested.stat().st_mode) == 0o700
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        assert validate_private_file(target, private_root=root) == target
        assert target.read_text(encoding="utf-8") == "synthetic ✓\n"
    finally:
        os.umask(previous_umask)


def test_exclusive_file_creation_preserves_existing_content(tmp_path: Path) -> None:
    root = ensure_private_root(tmp_path / "private")
    target = root / "ledger.jsonl"
    target.write_text("sentinel", encoding="utf-8")

    with pytest.raises(DataValidationError) as error:
        create_private_file(target, private_root=root)

    assert error.value.code == "private_file_exists"
    assert target.read_text(encoding="utf-8") == "sentinel"


def test_creation_rejects_destinations_outside_explicit_private_root(tmp_path: Path) -> None:
    root = ensure_private_root(tmp_path / "private")
    target = tmp_path / "outside.jsonl"

    with pytest.raises(PolicyViolation) as error:
        create_private_file(target, private_root=root)

    assert error.value.code == "private_path_outside_root"
    assert not target.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission modes are not Windows ACLs")
def test_existing_unsafe_root_and_file_modes_fail_without_repair(tmp_path: Path) -> None:
    unsafe_root = tmp_path / "unsafe-root"
    previous_umask = os.umask(0o022)
    try:
        unsafe_root.mkdir(mode=0o755)
        before_root_mode = stat.S_IMODE(unsafe_root.stat().st_mode)
        with pytest.raises(PolicyViolation) as root_error:
            ensure_private_root(unsafe_root)
        assert root_error.value.code == "private_root_permissions"
        assert stat.S_IMODE(unsafe_root.stat().st_mode) == before_root_mode

        root = ensure_private_root(tmp_path / "safe-root")
        unsafe_file = root / "public.jsonl"
        descriptor = os.open(unsafe_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(descriptor)
        before_file_mode = stat.S_IMODE(unsafe_file.stat().st_mode)
        with pytest.raises(PolicyViolation) as file_error:
            validate_private_file(unsafe_file, private_root=root)
        assert file_error.value.code == "private_file_permissions"
        assert stat.S_IMODE(unsafe_file.stat().st_mode) == before_file_mode
    finally:
        os.umask(previous_umask)


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership is not a Windows ACL")
def test_foreign_owner_root_fails_closed_without_chown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = ensure_private_root(tmp_path / "private")
    actual_user = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: actual_user + 1)

    with pytest.raises(PolicyViolation) as error:
        validate_private_file(root / "not-created.jsonl", private_root=root)

    assert error.value.code == "private_root_owner"
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership is not a Windows ACL")
def test_foreign_owner_file_fails_closed_without_chown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = ensure_private_root(tmp_path / "private")
    target = root / "ledger.jsonl"
    create_private_file(target, private_root=root)
    actual_user = os.geteuid()
    foreign_user = actual_user + 1
    original_stat = Path.stat

    def root_stat(path: Path, *args: object, **kwargs: object) -> object:
        result = original_stat(path, *args, **kwargs)
        if path != root:
            return result
        return SimpleNamespace(st_mode=result.st_mode, st_uid=foreign_user)

    monkeypatch.setattr(Path, "stat", root_stat)
    monkeypatch.setattr(os, "geteuid", lambda: foreign_user)

    with pytest.raises(PolicyViolation) as error:
        validate_private_file(target, private_root=root)

    assert error.value.code == "private_file_owner"


@pytest.mark.skipif(os.name != "posix", reason="POSIX hard-link fixture")
def test_existing_hard_linked_file_fails_closed(tmp_path: Path) -> None:
    root = ensure_private_root(tmp_path / "private")
    target = root / "ledger.jsonl"
    create_private_file(target, private_root=root)
    alias = tmp_path / "external-alias.jsonl"
    os.link(target, alias)

    with pytest.raises(DataValidationError) as error:
        validate_private_file(target, private_root=root)

    assert error.value.code == "private_file_link_rejected"
    assert alias.is_file()


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink fixture")
def test_creation_rejects_symlink_destination_without_touching_target(tmp_path: Path) -> None:
    root = ensure_private_root(tmp_path / "private")
    outside = tmp_path / "outside.txt"
    outside.write_text("sentinel", encoding="utf-8")
    target = root / "linked.txt"
    target.symlink_to(outside)

    with pytest.raises(DataValidationError) as error:
        create_private_file(target, private_root=root)

    assert error.value.code == "private_path_link_rejected"
    assert outside.read_text(encoding="utf-8") == "sentinel"
