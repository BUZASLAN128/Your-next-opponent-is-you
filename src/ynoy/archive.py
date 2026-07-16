from __future__ import annotations

import hashlib
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from ynoy.constants import (
    DEFAULT_ARCHIVE_MAX_COMPRESSION_RATIO,
    DEFAULT_ARCHIVE_MAX_ENTRIES,
    DEFAULT_ARCHIVE_MAX_ENTRY_BYTES,
    DEFAULT_ARCHIVE_MAX_JSON_ITEM_BYTES,
    DEFAULT_ARCHIVE_MAX_SOURCE_BYTES,
    DEFAULT_ARCHIVE_MAX_UNCOMPRESSED_BYTES,
    DEFAULT_JSON_MAX_NESTING,
)
from ynoy.errors import DataValidationError
from ynoy.json_stream import iter_json_object_array as iter_json_object_array


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_entries: int = DEFAULT_ARCHIVE_MAX_ENTRIES
    max_source_bytes: int = DEFAULT_ARCHIVE_MAX_SOURCE_BYTES
    max_total_uncompressed_bytes: int = DEFAULT_ARCHIVE_MAX_UNCOMPRESSED_BYTES
    max_entry_bytes: int = DEFAULT_ARCHIVE_MAX_ENTRY_BYTES
    max_json_item_bytes: int = DEFAULT_ARCHIVE_MAX_JSON_ITEM_BYTES
    max_json_nesting: int = DEFAULT_JSON_MAX_NESTING
    max_compression_ratio: float = DEFAULT_ARCHIVE_MAX_COMPRESSION_RATIO


def _is_unsafe_name(name: str) -> bool:
    if "\x00" in name or "\\" in name:
        return True
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    return (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    )


def _is_symlink(info: ZipInfo) -> bool:
    unix_mode = info.external_attr >> 16
    return stat.S_IFMT(unix_mode) == stat.S_IFLNK


def validate_zip_infos(infos: Sequence[ZipInfo], limits: ArchiveLimits) -> None:
    if len(infos) > limits.max_entries:
        raise DataValidationError(
            "archive_entry_limit",
            "Archive contains more entries than the configured safety limit.",
            details={"entry_count": len(infos), "limit": limits.max_entries},
        )
    total = 0
    for info in infos:
        _validate_zip_info(info, limits)
        total += info.file_size
        if total > limits.max_total_uncompressed_bytes:
            raise DataValidationError(
                "archive_expansion_limit",
                "Archive exceeds the configured total uncompressed limit.",
                details={"limit": limits.max_total_uncompressed_bytes},
            )


def _validate_zip_info(info: ZipInfo, limits: ArchiveLimits) -> None:
    if _is_unsafe_name(info.filename):
        raise DataValidationError("archive_path_unsafe", "Archive contains an unsafe member path.")
    if _is_symlink(info):
        raise DataValidationError("archive_link_rejected", "Archive links are not accepted.")
    if info.file_size > limits.max_entry_bytes:
        raise DataValidationError(
            "archive_member_too_large",
            "Archive member exceeds the configured uncompressed limit.",
            details={"limit": limits.max_entry_bytes},
        )
    ratio = info.file_size / max(info.compress_size, 1) if info.file_size else 0.0
    if ratio > limits.max_compression_ratio:
        raise DataValidationError(
            "archive_compression_ratio",
            "Archive member exceeds the configured compression-ratio limit.",
            details={"limit": limits.max_compression_ratio},
        )


def validate_archive_source(path: Path, limits: ArchiveLimits) -> int:
    try:
        source_size = path.stat().st_size
    except OSError as exc:
        raise DataValidationError(
            "archive_invalid", "The selected ZIP archive cannot be inspected."
        ) from exc
    if source_size > limits.max_source_bytes:
        raise DataValidationError(
            "archive_source_too_large",
            "Archive exceeds the configured source-file limit.",
            details={"limit": limits.max_source_bytes},
        )
    return source_size


def archive_sha256(path: Path, limits: ArchiveLimits, *, chunk_size: int = 1024 * 1024) -> str:
    validate_archive_source(path, limits)
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                total += len(chunk)
                if total > limits.max_source_bytes:
                    raise DataValidationError(
                        "archive_source_too_large",
                        "Archive grew beyond the configured source-file limit.",
                        details={"limit": limits.max_source_bytes},
                    )
                digest.update(chunk)
    except OSError as exc:
        raise DataValidationError(
            "archive_invalid", "The selected ZIP archive cannot be read."
        ) from exc
    return digest.hexdigest()


def open_validated_zip(path: str | Path, limits: ArchiveLimits) -> ZipFile:
    source = Path(path)
    validate_archive_source(source, limits)
    try:
        archive = ZipFile(source, mode="r", allowZip64=True)
        validate_zip_infos(archive.infolist(), limits)
        return archive
    except (BadZipFile, OSError) as exc:
        raise DataValidationError(
            "archive_invalid", "The selected ZIP archive is invalid."
        ) from exc
