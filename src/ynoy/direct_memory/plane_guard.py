from __future__ import annotations

import os
from pathlib import Path

from ynoy.direct_memory.data_plane import DataPlane
from ynoy.errors import DataValidationError
from ynoy.models import DataClass, InteractionReceipt, InteractionReview
from ynoy.private_files import validate_private_file


def validate_sqlite_storage(
    path: Path, private_root: Path, *, require_database: bool = True
) -> bool:
    """Validate a SQLite file and any existing journal, WAL, or SHM sidecars."""
    if require_database:
        validate_private_file(path, private_root=private_root)
    sidecars = (Path(f"{path}{suffix}") for suffix in ("-wal", "-shm", "-journal"))
    found = False
    for sidecar in sidecars:
        if os.path.lexists(sidecar):
            validate_private_file(sidecar, private_root=private_root)
            found = True
    return found


def assert_sqlite_initial_state(
    path: Path,
    private_root: Path,
    data_plane: DataPlane,
    schema_version: int,
    *,
    newly_created: bool,
) -> None:
    sidecars = validate_sqlite_storage(path, private_root)
    empty = path.stat().st_size == 0
    if empty != newly_created or (newly_created and sidecars):
        raise DataValidationError(
            "direct_memory_database_identity", "SQLite file state cannot initialize this store."
        )
    if not newly_created:
        assert_sqlite_header(path, data_plane, schema_version)


def assert_sqlite_header(path: Path, data_plane: DataPlane, schema_version: int) -> None:
    try:
        with path.open("rb") as stream:
            header = stream.read(100)
    except OSError as exc:
        raise DataValidationError(
            "direct_memory_database_identity", "SQLite database header could not be read."
        ) from exc
    if (
        len(header) != 100
        or header[:16] != b"SQLite format 3\x00"
        or int.from_bytes(header[60:64], "big") != schema_version
        or int.from_bytes(header[68:72], "big") != data_plane.application_id
    ):
        raise DataValidationError(
            "direct_memory_database_identity", "SQLite database plane or version is invalid."
        )


def assert_no_orphaned_sqlite_sidecars(path: Path, private_root: Path) -> None:
    if validate_sqlite_storage(path, private_root, require_database=False):
        raise DataValidationError(
            "direct_memory_database_identity", "SQLite sidecars lack their database file."
        )


def assert_review_data_plane(
    value: InteractionReceipt | InteractionReview, data_plane: DataPlane
) -> None:
    classes: tuple[DataClass, ...]
    if isinstance(value, InteractionReview):
        source = value.source
        classes = (source.source_data_class, value.source_data_class, value.review_data_class)
    else:
        source = value
        classes = (source.source_data_class,)
    private_ok = not source.synthetic and DataClass.PUBLIC_SYNTHETIC not in classes
    synthetic_ok = source.synthetic and all(
        item == DataClass.PUBLIC_SYNTHETIC for item in classes
    )
    if (data_plane == DataPlane.PRIVATE and not private_ok) or (
        data_plane == DataPlane.PUBLIC_SYNTHETIC and not synthetic_ok
    ):
        raise DataValidationError(
            "direct_memory_data_plane_mismatch",
            "Review source classification does not match its direct-memory plane.",
        )


__all__ = [
    "assert_no_orphaned_sqlite_sidecars",
    "assert_review_data_plane",
    "assert_sqlite_header",
    "assert_sqlite_initial_state",
    "validate_sqlite_storage",
]
