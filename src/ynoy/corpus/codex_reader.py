from __future__ import annotations

import json
import os
import stat

from ynoy.corpus.codex_discovery import DiscoveredCodexFile
from ynoy.errors import DataValidationError
from ynoy.models.codex_inventory import FirstRecordState


def inspect_first_record(item: DiscoveredCodexFile, limit: int) -> FirstRecordState:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(item.path, flags)
    except OSError as exc:
        raise DataValidationError(
            "codex_session_unreadable", "A canonical Codex session file is unreadable."
        ) from exc
    try:
        before = os.fstat(descriptor)
        current = os.stat(item.path, follow_symlinks=False)
        _validate_opened_file(item, before, current)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            prefix = stream.readline(limit + 1)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise DataValidationError(
            "codex_session_unreadable", "A canonical Codex session file is unreadable."
        ) from exc
    finally:
        os.close(descriptor)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DataValidationError(
            "codex_source_changed_during_inventory",
            "A Codex session file changed during metadata inventory.",
        )
    return _classify_prefix(prefix, limit)


def _validate_opened_file(
    item: DiscoveredCodexFile, opened: os.stat_result, current: os.stat_result
) -> None:
    if not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(current.st_mode):
        raise DataValidationError(
            "codex_link_swap_rejected", "Codex session inspection requires a stable regular file."
        )
    expected_identity = item.device, item.inode
    if expected_identity != (opened.st_dev, opened.st_ino):
        raise DataValidationError(
            "codex_link_swap_rejected", "Codex session identity changed before inspection."
        )
    if expected_identity != (current.st_dev, current.st_ino):
        raise DataValidationError(
            "codex_link_swap_rejected", "Codex session path changed before inspection."
        )
    expected = item.file_bytes, item.modified_ns
    if expected != (opened.st_size, opened.st_mtime_ns):
        raise DataValidationError(
            "codex_source_changed_during_inventory",
            "A Codex session file changed before metadata inventory could read it.",
        )


def _classify_prefix(prefix: bytes, limit: int) -> FirstRecordState:
    if not prefix:
        return "empty"
    if len(prefix) > limit and not prefix.endswith(b"\n"):
        return "oversized_first_record"
    try:
        payload = json.loads(prefix)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid_first_record"
    if isinstance(payload, dict) and payload.get("type") == "session_meta":
        return "session_meta"
    return "invalid_first_record"
