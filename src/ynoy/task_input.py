from __future__ import annotations

from ynoy.errors import DataValidationError

MAX_TASK_BYTES = 64 * 1024


def validate_task(value: str) -> str:
    """Return a bounded non-empty task or fail before any adapter sees it."""
    task = value.strip()
    if not task:
        raise DataValidationError("task_required", "Task must not be empty.")
    if len(task.encode("utf-8")) > MAX_TASK_BYTES:
        raise DataValidationError(
            "task_size_limit", "Task exceeds the 64 KiB local inference limit."
        )
    return task
