from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import validate_next_head
from ynoy.models.full_persona import FullCorpusHead, FullCorpusManifest
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file

_HEAD = re.compile(r"^(?P<revision>[0-9]{8})\.json$")
_HEAD_TEMP = re.compile(r"^\.(?P<revision>[0-9]{8})\.json\.[0-9a-f]{32}\.tmp$")
_SHARD = re.compile(r"^(?P<revision>[0-9]{8})\.jsonl\.gz$")
_SHARD_RECEIPT = re.compile(r"^(?P<revision>[0-9]{8})\.jsonl\.receipt\.json$")
_SHARD_RECEIPT_TEMP = re.compile(
    r"^\.(?P<revision>[0-9]{8})\.jsonl\.receipt\.json\.[0-9a-f]{32}\.tmp$"
)
_FILE = re.compile(r"^(?P<index>[0-9]{8})\.json$")
_FILE_TEMP = re.compile(r"^\.(?P<index>[0-9]{8})\.json\.[0-9a-f]{32}\.tmp$")
_POINTER_TEMP = re.compile(r"^\.head\.json\.[0-9a-f]{32}\.tmp$")
_STAGING = re.compile(r"^[0-9a-f]{32}\.jsonl\.gz\.tmp$")
_CONTROL_BYTES = 16 * 1024**2


def recover_interrupted_run(
    store: FullPersonaStore, manifest: FullCorpusManifest, current: FullCorpusHead
) -> FullCorpusHead:
    """Discard only a validated uncommitted next-revision cohort."""
    run = store.run_path(manifest.run_id)
    candidate, head_deletions = _inspect_heads(run / "heads", current)
    _validate_candidate(current, candidate)
    deletions: list[Path] = []
    deletions.extend(_inspect_root(run, candidate))
    deletions.extend(_inspect_shards(run / "shards", current, candidate))
    deletions.extend(_inspect_files(run / "files", current, candidate))
    deletions.extend(_inspect_staging(store.staging_run_path(manifest.run_id)))
    deletions.extend(head_deletions)
    for path in deletions:
        require_regular_file(path)
    for path in deletions:
        path.unlink()
    verify_committed_run(store, manifest, current)
    return current


def _inspect_root(run: Path, candidate: FullCorpusHead | None) -> list[Path]:
    allowed = {"manifest.json", "head.json", "heads", "shards", "files"}
    deletions: list[Path] = []
    for path in run.iterdir():
        reject_link_if_present(path)
        if path.name in allowed:
            continue
        if _POINTER_TEMP.fullmatch(path.name) and candidate is not None:
            deletions.append(path)
            continue
        _recovery_error("run root contains an unrecognized artifact")
    return deletions


def _inspect_heads(root: Path, current: FullCorpusHead) -> tuple[FullCorpusHead | None, list[Path]]:
    _require_directory(root)
    candidate: FullCorpusHead | None = None
    deletions: list[Path] = []
    next_revision = current.revision + 1
    for path in root.iterdir():
        reject_link_if_present(path)
        match = _HEAD.fullmatch(path.name)
        temporary = _HEAD_TEMP.fullmatch(path.name)
        if temporary and int(temporary.group("revision")) == next_revision:
            deletions.append(path)
        elif match and int(match.group("revision")) <= current.revision:
            continue
        elif match and int(match.group("revision")) == next_revision and candidate is None:
            candidate = _read_head(path)
            deletions.append(path)
        else:
            _recovery_error("head directory contains an invalid recovery tail")
    return candidate, deletions


def _inspect_shards(
    root: Path, current: FullCorpusHead, candidate: FullCorpusHead | None
) -> list[Path]:
    _require_directory(root)
    next_revision = current.revision + 1
    expects_tail = candidate is not None and candidate.shard_count == current.shard_count + 1
    deletions: list[Path] = []
    for path in root.iterdir():
        reject_link_if_present(path)
        match = _SHARD.fullmatch(path.name) or _SHARD_RECEIPT.fullmatch(path.name)
        temporary = _SHARD_RECEIPT_TEMP.fullmatch(path.name)
        if match and int(match.group("revision")) <= current.revision:
            continue
        if match and int(match.group("revision")) == next_revision and expects_tail:
            deletions.append(path)
            continue
        if temporary and int(temporary.group("revision")) == next_revision and expects_tail:
            deletions.append(path)
            continue
        _recovery_error("shard directory contains an invalid recovery tail")
    return deletions


def _inspect_files(
    root: Path, current: FullCorpusHead, candidate: FullCorpusHead | None
) -> list[Path]:
    _require_directory(root)
    expects_tail = candidate is not None and candidate.file_index == current.file_index + 1
    deletions: list[Path] = []
    for path in root.iterdir():
        reject_link_if_present(path)
        match = _FILE.fullmatch(path.name)
        temporary = _FILE_TEMP.fullmatch(path.name)
        if match and int(match.group("index")) < current.file_index:
            continue
        if match and int(match.group("index")) == current.file_index and expects_tail:
            deletions.append(path)
            continue
        if temporary and int(temporary.group("index")) == current.file_index and expects_tail:
            deletions.append(path)
            continue
        _recovery_error("file receipt directory contains an invalid recovery tail")
    return deletions


def _inspect_staging(root: Path) -> list[Path]:
    if not root.exists():
        return []
    _require_directory(root)
    values: list[Path] = []
    for path in root.iterdir():
        reject_link_if_present(path)
        if not _STAGING.fullmatch(path.name):
            _recovery_error("staging contains an unrecognized artifact")
        values.append(path)
    return values


def _validate_candidate(current: FullCorpusHead, candidate: FullCorpusHead | None) -> None:
    if candidate is None:
        return
    validate_next_head(current, candidate)
    if candidate.shard_count not in {current.shard_count, current.shard_count + 1}:
        _recovery_error("candidate shard count is not a single commit")
    if candidate.file_index not in {current.file_index, current.file_index + 1}:
        _recovery_error("candidate file index is not a single commit")
    if candidate.shard_count == current.shard_count and (
        candidate.last_shard_sha256 != current.last_shard_sha256
    ):
        _recovery_error("candidate changed the shard tail without a shard")


def _read_head(path: Path) -> FullCorpusHead:
    try:
        require_regular_file(path)
        with path.open("rb") as stream:
            raw = stream.read(_CONTROL_BYTES + 1)
        if len(raw) > _CONTROL_BYTES:
            raise ValueError
        return FullCorpusHead.model_validate_json(raw)
    except (OSError, ValidationError, ValueError) as exc:
        raise DataValidationError(
            "full_persona_recovery_invalid", "The interrupted revision cannot be recovered."
        ) from exc


def _require_directory(path: Path) -> None:
    reject_link_if_present(path)
    if not path.is_dir():
        _recovery_error("a required recovery directory is missing")


def _recovery_error(reason: str) -> None:
    raise DataValidationError(
        "full_persona_recovery_invalid",
        "The interrupted full-persona run failed closed.",
        details={"reason": reason},
    )
