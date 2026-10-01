"""Create and validate files beneath an explicit private storage root.

On POSIX, newly created directories and files use modes 0700 and 0600. Existing
paths are checked and never chmodded. Windows permissions come from inherited
ACLs; this module does not inspect or guarantee Windows ACL protection.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import TextIO

from ynoy.errors import DataValidationError, PolicyViolation, StorageError
from ynoy.policy import assert_outside_git

_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600


def ensure_private_root(root: Path) -> Path:
    """Create or validate an explicit private root, returning its absolute path."""
    candidate = _absolute_path(root)
    assert_outside_git(candidate)
    _ensure_directory_tree(candidate)
    _validate_private_directory(candidate, root=True)
    return candidate


def create_private_parents(directory: Path, *, private_root: Path) -> Path:
    """Create contained parent directories with private POSIX modes."""
    root = ensure_private_root(private_root)
    target = _absolute_path(directory)
    relative = _contained_relative(root, target, allow_root=True)
    current = root
    _validate_private_directory(current, root=True)
    for part in relative.parts:
        current /= part
        _ensure_directory_tree(current)
        _validate_private_directory(current)
    return target


def create_private_file(path: Path, *, private_root: Path) -> Path:
    """Exclusively create an empty private file; never replace an existing path."""
    descriptor = _open_exclusive_descriptor(path, private_root=private_root)
    try:
        os.close(descriptor)
    except OSError as exc:
        raise StorageError(
            "private_file_create_failed", "Private file could not be created."
        ) from exc
    return _absolute_path(path)


def open_exclusive_private_utf8(path: Path, *, private_root: Path) -> TextIO:
    """Exclusively create a UTF-8 text file beneath the private root."""
    descriptor = _open_exclusive_descriptor(path, private_root=private_root)
    try:
        return os.fdopen(descriptor, "w", encoding="utf-8", newline="")
    except OSError as exc:
        _close_and_remove_created_file(descriptor, _absolute_path(path))
        raise StorageError("private_file_open_failed", "Private file could not be opened.") from exc


def validate_private_file(path: Path, *, private_root: Path) -> Path:
    """Validate an existing regular private file without changing it."""
    root = _absolute_path(private_root)
    assert_outside_git(root)
    _validate_private_directory(root, root=True)
    target = _absolute_path(path)
    relative = _contained_relative(root, target, allow_root=False)
    current = root
    for part in relative.parts[:-1]:
        current /= part
        _validate_private_directory(current)
    _validate_private_file(target)
    return target


def _open_exclusive_descriptor(path: Path, *, private_root: Path) -> int:
    root = ensure_private_root(private_root)
    target = _absolute_path(path)
    _contained_relative(root, target, allow_root=False)
    create_private_parents(target.parent, private_root=root)
    _reject_link(target)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags, _PRIVATE_FILE_MODE)
    except FileExistsError as exc:
        raise DataValidationError(
            "private_file_exists", "Refusing to overwrite an existing private file."
        ) from exc
    except OSError as exc:
        raise StorageError(
            "private_file_create_failed", "Private file could not be created."
        ) from exc
    try:
        _validate_new_file_mode(descriptor)
    except Exception:
        _close_and_remove_created_file(descriptor, target)
        raise
    return descriptor


def _ensure_directory_tree(directory: Path) -> None:
    missing: list[Path] = []
    current = directory
    while not _lexists(current):
        missing.append(current)
        if current.parent == current:
            raise StorageError(
                "private_directory_create_failed", "Private directory is unavailable."
            )
        current = current.parent
    _validate_real_directory(current)
    for candidate in reversed(missing):
        _reject_link(candidate)
        try:
            candidate.mkdir(mode=_PRIVATE_DIRECTORY_MODE)
        except FileExistsError:
            pass
        except OSError as exc:
            raise StorageError(
                "private_directory_create_failed", "Private directory could not be created."
            ) from exc
        _validate_private_directory(candidate)


def _validate_private_directory(path: Path, *, root: bool = False) -> None:
    _validate_real_directory(path)
    if os.name != "posix":
        return
    try:
        directory_stat = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise DataValidationError(
            "private_directory_invalid", "Private storage path must be a directory."
        ) from exc
    if directory_stat.st_uid != _current_uid():
        code = "private_root_owner" if root else "private_directory_owner"
        raise PolicyViolation(code, "Private directories must be owned by the current user.")
    mode = stat.S_IMODE(directory_stat.st_mode)
    if mode & 0o077 or mode & 0o7000 or mode & 0o700 != 0o700:
        code = "private_root_permissions" if root else "private_directory_permissions"
        raise PolicyViolation(code, "Private directories must deny group and other access.")


def _validate_private_file(path: Path) -> None:
    _reject_link(path)
    try:
        file_stat = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise DataValidationError("private_file_invalid", "Private file is unavailable.") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise DataValidationError("private_file_invalid", "Private file must be a regular file.")
    if os.name == "posix":
        if file_stat.st_nlink != 1:
            raise DataValidationError(
                "private_file_link_rejected", "Private files cannot have hard-link aliases."
            )
        if file_stat.st_uid != _current_uid():
            raise PolicyViolation(
                "private_file_owner", "Private files must be owned by the current user."
            )
        mode = stat.S_IMODE(file_stat.st_mode)
        if mode & 0o077 or mode & 0o7111:
            raise PolicyViolation(
                "private_file_permissions", "Private files must deny group and other access."
            )


def _validate_new_file_mode(descriptor: int) -> None:
    if os.name != "posix":
        return
    file_stat = os.fstat(descriptor)
    if file_stat.st_nlink != 1:
        raise DataValidationError(
            "private_file_link_rejected", "Private files cannot have hard-link aliases."
        )
    if file_stat.st_uid != _current_uid():
        raise PolicyViolation(
            "private_file_owner", "Private files must be owned by the current user."
        )
    actual = stat.S_IMODE(file_stat.st_mode)
    if actual != _PRIVATE_FILE_MODE:
        raise PolicyViolation(
            "private_file_permissions", "New private files must use owner-only POSIX permissions."
        )


def _validate_real_directory(path: Path) -> None:
    _reject_link(path)
    try:
        valid = path.is_dir()
    except OSError:
        valid = False
    if not valid:
        raise DataValidationError(
            "private_directory_invalid", "Private storage path must be a directory."
        )


def _contained_relative(root: Path, target: Path, *, allow_root: bool) -> Path:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise PolicyViolation(
            "private_path_outside_root", "Private files must stay inside the explicit private root."
        ) from exc
    if not allow_root and relative == Path("."):
        raise DataValidationError("private_file_invalid", "A private file path is required.")
    return relative


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _current_uid() -> int:
    getter: object = getattr(os, "geteuid", None)
    if not callable(getter):
        raise StorageError(
            "private_owner_unavailable", "POSIX file ownership could not be checked."
        )
    user_id = getter()
    if not isinstance(user_id, int):
        raise StorageError(
            "private_owner_unavailable", "POSIX file ownership could not be checked."
        )
    return user_id


def _reject_link(path: Path) -> None:
    is_junction = getattr(path, "is_junction", lambda: False)
    if path.is_symlink() or bool(is_junction()):
        raise DataValidationError(
            "private_path_link_rejected", "Private storage cannot use links or junctions."
        )


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _close_and_remove_created_file(descriptor: int, path: Path) -> None:
    try:
        created = os.fstat(descriptor)
    except OSError:
        created = None
    try:
        os.close(descriptor)
    except OSError:
        pass
    if created is None:
        return
    try:
        current = path.stat(follow_symlinks=False)
        if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
            path.unlink()
    except OSError:
        pass
