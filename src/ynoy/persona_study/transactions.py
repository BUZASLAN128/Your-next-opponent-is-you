from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactIndex
from ynoy.persona_study.storage_paths import (
    StudyStoragePaths,
    reject_link_if_present,
)


@contextmanager
def exclusive_study_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_link_if_present(path.parent)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"persona-study-transaction/0.1")
        os.fsync(descriptor)
        yield
    except FileExistsError as exc:
        raise DataValidationError(
            "persona_study_locked",
            "Another process or an interrupted transaction owns this study lock.",
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
            if path.exists():
                path.unlink()


def exclusive_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_link_if_present(path.parent)
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except FileExistsError as exc:
        raise DataValidationError(
            "persona_study_artifact_exists", "Refusing to overwrite a study artifact."
        ) from exc
    except Exception:
        if created and path.exists():
            path.unlink()
        raise


def require_index_matches_disk(paths: StudyStoragePaths, index: StudyArtifactIndex) -> None:
    expected = _expected_files(index)
    actual = {
        "control": _relative_files(paths.control_run(index.study_id)),
        "annotator": _relative_files(paths.run_paths(index.study_id)[1]),
        "evaluator": _relative_files(paths.run_paths(index.study_id)[2]),
    }
    if actual != expected:
        raise DataValidationError(
            "persona_study_inventory_mismatch",
            "The private study index does not match its actual scoped files.",
        )


def _expected_files(index: StudyArtifactIndex) -> dict[str, set[str]]:
    expected = {"control": {"index.json"}, "annotator": set(), "evaluator": set()}
    for entry in index.entries:
        scope, relative = entry.relative_path.split("/", 1)
        expected[scope].add(relative)
    return expected


def _relative_files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    reject_link_if_present(root)
    files: set[str] = set()
    for path in root.rglob("*"):
        reject_link_if_present(path)
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    return files
