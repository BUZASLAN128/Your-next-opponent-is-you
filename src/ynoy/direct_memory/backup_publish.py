from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Callable
from pathlib import Path

from ynoy.errors import DataValidationError


def backup_to_path(
    source: sqlite3.Connection, target: Path, validate: Callable[[Path], None]
) -> None:
    temporary = _temporary_path(target)
    backup: sqlite3.Connection | None = None
    try:
        backup = sqlite3.connect(temporary)
        source.backup(backup)
        backup.close()
        backup = None
        validate(temporary)
        try:
            _publish_without_overwrite(temporary, target)
        except FileExistsError as exc:
            raise DataValidationError(
                "direct_memory_backup_exists", "Backup refuses to overwrite an existing file."
            ) from exc
    finally:
        if backup is not None:
            try:
                backup.close()
            finally:
                _cleanup_temporary(temporary)
        else:
            _cleanup_temporary(temporary)


def _temporary_path(target: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".backup.tmp", dir=target.parent
    )
    os.close(descriptor)
    return Path(name)


def _publish_without_overwrite(temporary: Path, target: Path) -> None:
    if os.name == "nt":
        os.rename(temporary, target)
    else:
        os.link(temporary, target)


def _cleanup_temporary(temporary: Path) -> None:
    for path in (
        temporary,
        Path(f"{temporary}-journal"),
        Path(f"{temporary}-wal"),
        Path(f"{temporary}-shm"),
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


__all__ = ["backup_to_path"]
