from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from typing import BinaryIO

from ynoy.errors import DataValidationError
from ynoy.persona_study.storage_paths import reject_link_if_present


@contextmanager
def exclusive_run_lock(path: Path) -> Iterator[None]:
    """Hold an OS lock that is released automatically when the process exits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_link_if_present(path.parent)
    reject_link_if_present(path)
    with path.open("a+b") as handle:
        _prepare_lock_file(handle)
        try:
            _acquire(handle)
        except OSError as exc:
            raise DataValidationError(
                "persona_study_locked",
                "Another process currently owns this full-persona run lock.",
            ) from exc
        try:
            yield
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
