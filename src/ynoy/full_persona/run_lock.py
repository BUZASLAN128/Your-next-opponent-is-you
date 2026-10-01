from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from importlib import import_module
from pathlib import Path
from typing import BinaryIO, Literal, overload

from ynoy.errors import DataValidationError
from ynoy.persona_study.storage_paths import reject_link_if_present


@overload
def exclusive_run_lock(
    path: Path, *, expose_handle: Literal[True]
) -> AbstractContextManager[BinaryIO]: ...


@overload
def exclusive_run_lock(
    path: Path, *, expose_handle: Literal[False] = False
) -> AbstractContextManager[None]: ...


def exclusive_run_lock(
    path: Path, *, expose_handle: bool = False
) -> AbstractContextManager[BinaryIO | None]:
    """Hold an OS lock; optionally expose its open handle to the lock owner."""
    return _exclusive_run_lock(path, expose_handle=expose_handle)


@contextmanager
def _exclusive_run_lock(path: Path, *, expose_handle: bool) -> Iterator[BinaryIO | None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_link_if_present(path.parent)
    reject_link_if_present(path)
    with path.open("a+b") as handle:
        try:
            _acquire(handle)
        except OSError as exc:
            raise DataValidationError(
                "persona_study_locked",
                "Another process currently owns this full-persona run lock.",
            ) from exc
        try:
            _prepare_lock_file(handle)
            yield handle if expose_handle else None
        finally:
            _release(handle)


def _prepare_lock_file(handle: BinaryIO) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"full-persona-os-lock/0.1")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(handle.name, 0o600)
    except OSError:
        pass


def _acquire(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    fcntl = import_module("fcntl")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    fcntl = import_module("fcntl")
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
