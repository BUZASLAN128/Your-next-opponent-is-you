from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from ynoy.corpus.codex import assert_synthetic_codex_root, codex_source_key
from ynoy.corpus.codex_discovery import (
    CodexInventoryLimits,
    DiscoveredCodexFile,
    discover_codex_sessions,
    discovery_key,
    resolve_codex_root,
)
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.models import (
    DataClass,
    PersonaStudyManifest,
    ProtectedHoldoutFreeze,
    StudyArtifactIndex,
)
from ynoy.models.full_persona import FullCorpusLimits, FullCorpusManifest, FullCorpusSource
from ynoy.persona_study.lineage import component_lineages, read_lineage, session_start_ns
from ynoy.persona_study.storage_paths import StudyStoragePaths, require_regular_file
from ynoy.policy import require_private_root
from ynoy.util import canonical_sha256, sha256_bytes, utc_now

_CONTROL_LIMIT = 16 * 1024**2


def freeze_full_corpus(
    source_root: Path,
    private_root: Path,
    source_study_id: str,
    *,
    synthetic: bool,
    limits: FullCorpusLimits | None = None,
) -> FullCorpusManifest:
    """Hash every canonical pre-holdout file into one immutable private manifest."""
    chosen = limits or FullCorpusLimits()
    study, freeze = _read_source_contract(private_root, source_study_id, synthetic)
    root = resolve_codex_root(source_root)
    if synthetic:
        assert_synthetic_codex_root(root)
    inventory_limits = CodexInventoryLimits(
        max_files=chosen.max_manifest_files,
        max_entries=200_000,
        max_depth=8,
    )
    before = discover_codex_sessions(root, inventory_limits)
    eligible = tuple(
        item
        for item in before.files
        if item.file_bytes > 0 and session_start_ns(item) < freeze.boundary_session_start_ns
    )
    if not eligible:
        raise DataValidationError(
            "full_persona_source_empty", "No canonical pre-holdout source is available."
        )
    sources = _freeze_sources(eligible)
    after = discover_codex_sessions(root, inventory_limits)
    if discovery_key(before) != discovery_key(after):
        raise DataValidationError(
            "full_persona_source_universe_changed",
            "The canonical source universe changed while it was frozen.",
        )
    return _seal_manifest(study, freeze, sources, chosen, synthetic)


def _read_source_contract(
    private_root: Path, source_study_id: str, synthetic: bool
) -> tuple[PersonaStudyManifest, ProtectedHoldoutFreeze]:
    root = require_private_root(private_root, real_data=not synthetic).root
    paths = StudyStoragePaths(root)
    try:
        index = StudyArtifactIndex.model_validate_json(_read_bounded(paths.index(source_study_id)))
        if index.expires_at <= utc_now():
            raise ValueError("source study expired")
        manifest_raw = _read_indexed_artifact(paths, index, "evaluator/manifest.json")
        freeze_raw = _read_indexed_artifact(paths, index, "evaluator/protected-holdout-freeze.json")
        study = PersonaStudyManifest.model_validate_json(manifest_raw)
        freeze = ProtectedHoldoutFreeze.model_validate_json(freeze_raw)
    except (OSError, ValidationError, ValueError) as exc:
        raise DataValidationError(
            "full_persona_source_study_invalid",
            "The protected source-study contract is invalid.",
        ) from exc
    expected = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS
    if study.source_data_class != expected or freeze.source_data_class != expected:
        raise DataValidationError(
            "full_persona_source_mode_mismatch", "The source-study mode does not match."
        )
    if study.protected_holdout_freeze_sha256 != freeze.freeze_sha256:
        raise DataValidationError(
            "full_persona_holdout_binding_mismatch", "The protected holdout binding is invalid."
        )
    return study, freeze


def _read_indexed_artifact(
    paths: StudyStoragePaths, index: StudyArtifactIndex, relative_path: str
) -> bytes:
    matches = tuple(item for item in index.entries if item.relative_path == relative_path)
    if len(matches) != 1 or matches[0].mutable_by != "none":
        raise ValueError("source contract entry is unavailable")
    value = _read_bounded(paths.artifact(index.study_id, relative_path))
    if sha256_bytes(value) != matches[0].sha256:
        raise ValueError("source contract entry hash mismatch")
    return value


def _read_bounded(path: Path) -> bytes:
    require_regular_file(path)
    with path.open("rb") as stream:
        value = stream.read(_CONTROL_LIMIT + 1)
    if len(value) > _CONTROL_LIMIT:
        raise ValueError("source control artifact exceeds bound")
    return value


def _freeze_sources(files: tuple[DiscoveredCodexFile, ...]) -> tuple[FullCorpusSource, ...]:
    lineages = component_lineages(tuple(read_lineage(item) for item in files))
    sources = tuple(_freeze_source(value.item, value) for value in lineages)
    return tuple(
        sorted(sources, key=lambda item: (item.session_start_ns, item.partition, item.source_key))
    )


def _freeze_source(item: DiscoveredCodexFile, lineage: Any) -> FullCorpusSource:
    digest = hashlib.sha256()
    with open_stable_codex_file(item) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    payload = {
        "partition": item.partition,
        "relative_locator": item.relative.as_posix(),
        "source_key": codex_source_key(item),
        "file_bytes": item.file_bytes,
        "modified_ns": item.modified_ns,
        "device": item.device,
        "inode": item.inode,
        "session_start_ns": lineage.session_start_ns,
        "thread_receipt": lineage.thread_receipt,
        "parent_thread_receipt": lineage.parent_receipt,
        "lineage_component_receipt": lineage.component_receipt,
        "blob_sha256": digest.hexdigest(),
    }
    return FullCorpusSource.model_validate({**payload, "source_receipt": canonical_sha256(payload)})


def _seal_manifest(
    study: PersonaStudyManifest,
    freeze: ProtectedHoldoutFreeze,
    sources: tuple[FullCorpusSource, ...],
    limits: FullCorpusLimits,
    synthetic: bool,
) -> FullCorpusManifest:
    source_snapshot = canonical_sha256([item.model_dump(mode="json") for item in sources])
    run_id = canonical_sha256(
        {
            "protocol": "full-persona-corpus/0.1",
            "study": study.study_id,
            "holdout": freeze.freeze_sha256,
            "sources": source_snapshot,
            "config": limits.config_sha256,
        }
    )
    latest_mtime = max(item.modified_ns for item in sources)
    created_at = max(study.created_at, datetime.fromtimestamp(latest_mtime / 1e9, tz=UTC))
    payload = {
        "run_id": run_id,
        "source_study_id": study.study_id,
        "holdout_freeze_sha256": freeze.freeze_sha256,
        "holdout_boundary_session_start_ns": freeze.boundary_session_start_ns,
        "stable_before_ns": latest_mtime,
        "created_at": created_at,
        "expires_at": created_at + timedelta(days=limits.retention_days),
        "limits": limits,
        "source_data_class": DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS,
        "synthetic": synthetic,
        "files": sources,
        "expected_file_count": len(sources),
        "expected_input_bytes": sum(item.file_bytes for item in sources),
        "source_snapshot_sha256": source_snapshot,
    }
    draft = cast(Any, FullCorpusManifest).model_construct(**payload, manifest_sha256="0" * 64)
    return FullCorpusManifest.model_validate(
        {
            **payload,
            "manifest_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"manifest_sha256"})
            ),
        }
    )
