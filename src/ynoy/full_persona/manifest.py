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
    resolve_codex_root,
)
from ynoy.corpus.codex_reader import open_stable_codex_file
from ynoy.errors import DataValidationError
from ynoy.full_persona.source_universe import (
    ExcludedSource,
    partition_sources,
    stability_cutoff_ns,
    verify_discovery_replay,
)
from ynoy.models import (
    DataClass,
    PersonaStudyManifest,
    ProtectedHoldoutFreeze,
    StudyArtifactIndex,
)
from ynoy.models.full_persona import FullCorpusLimits, FullCorpusManifest, FullCorpusSource
from ynoy.models.full_persona_exclusion import FullCorpusExclusion
from ynoy.persona_study.lineage import component_lineages, read_lineage
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
    boundary = freeze.boundary_session_start_ns
    stable_before_ns = stability_cutoff_ns(study, freeze)
    before = discover_codex_sessions(
        root,
        inventory_limits,
        session_start_before_ns=boundary,
    )
    eligible, excluded = partition_sources(before.files, stable_before_ns)
    if not eligible:
        raise DataValidationError(
            "full_persona_source_empty", "No canonical pre-holdout source is available."
        )
    sources = _freeze_sources(eligible, chosen.source_chunk_bytes)
    exclusions = _freeze_exclusions(excluded)
    after = discover_codex_sessions(
        root,
        inventory_limits,
        session_start_before_ns=boundary,
    )
    verify_discovery_replay(before, after, stable_before_ns)
    return _seal_manifest(study, freeze, sources, exclusions, stable_before_ns, chosen, synthetic)


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


def _freeze_sources(
    files: tuple[DiscoveredCodexFile, ...], chunk_size_bytes: int
) -> tuple[FullCorpusSource, ...]:
    lineages = component_lineages(tuple(read_lineage(item) for item in files))
    sources = tuple(_freeze_source(value.item, value, chunk_size_bytes) for value in lineages)
    return tuple(
        sorted(sources, key=lambda item: (item.session_start_ns, item.partition, item.source_key))
    )


def _freeze_exclusions(values: tuple[ExcludedSource, ...]) -> tuple[FullCorpusExclusion, ...]:
    exclusions = tuple(_freeze_exclusion(value) for value in values)
    return tuple(sorted(exclusions, key=lambda item: (item.partition, item.relative_locator)))


def _freeze_exclusion(value: ExcludedSource) -> FullCorpusExclusion:
    item = value.item
    payload = {
        "partition": item.partition,
        "relative_locator": item.relative.as_posix(),
        "source_key": codex_source_key(item),
        "observed_file_bytes": item.file_bytes,
        "observed_modified_ns": item.modified_ns,
        "device": item.device,
        "inode": item.inode,
        "reason": value.reason,
    }
    return FullCorpusExclusion.model_validate(
        {**payload, "exclusion_receipt": canonical_sha256(payload)}
    )


def _freeze_source(
    item: DiscoveredCodexFile, lineage: Any, chunk_size_bytes: int
) -> FullCorpusSource:
    blob_sha256, chunk_sha256 = _hash_source_chunks(item, chunk_size_bytes)
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
        "blob_sha256": blob_sha256,
        "chunk_size_bytes": chunk_size_bytes,
        "chunk_sha256": chunk_sha256,
    }
    return FullCorpusSource.model_validate({**payload, "source_receipt": canonical_sha256(payload)})


def _hash_source_chunks(
    item: DiscoveredCodexFile, chunk_size_bytes: int
) -> tuple[str, tuple[str, ...]]:
    digest = hashlib.sha256()
    chunks: list[str] = []
    with open_stable_codex_file(item) as stream:
        for chunk in iter(lambda: stream.read(chunk_size_bytes), b""):
            digest.update(chunk)
            chunks.append(hashlib.sha256(chunk).hexdigest())
    return digest.hexdigest(), tuple(chunks)


def _seal_manifest(
    study: PersonaStudyManifest,
    freeze: ProtectedHoldoutFreeze,
    sources: tuple[FullCorpusSource, ...],
    exclusions: tuple[FullCorpusExclusion, ...],
    stable_before_ns: int,
    limits: FullCorpusLimits,
    synthetic: bool,
) -> FullCorpusManifest:
    source_snapshot = canonical_sha256([item.model_dump(mode="json") for item in sources])
    exclusion_snapshot = canonical_sha256([item.model_dump(mode="json") for item in exclusions])
    run_id = _run_id(study, freeze, source_snapshot, exclusion_snapshot, limits)
    latest_mtime = max(item.modified_ns for item in sources)
    created_at = max(study.created_at, datetime.fromtimestamp(latest_mtime / 1e9, tz=UTC))
    payload = {
        "run_id": run_id,
        "source_study_id": study.study_id,
        "holdout_freeze_sha256": freeze.freeze_sha256,
        "holdout_boundary_session_start_ns": freeze.boundary_session_start_ns,
        "stable_before_ns": stable_before_ns,
        "created_at": created_at,
        "expires_at": created_at + timedelta(days=limits.retention_days),
        "limits": limits,
        "source_data_class": DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS,
        "synthetic": synthetic,
        "files": sources,
        "expected_file_count": len(sources),
        "expected_input_bytes": sum(item.file_bytes for item in sources),
        "source_snapshot_sha256": source_snapshot,
        "excluded_files": exclusions,
        "expected_excluded_file_count": len(exclusions),
        "exclusion_snapshot_sha256": exclusion_snapshot,
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


def _run_id(
    study: PersonaStudyManifest,
    freeze: ProtectedHoldoutFreeze,
    source_snapshot: str,
    exclusion_snapshot: str,
    limits: FullCorpusLimits,
) -> str:
    return canonical_sha256(
        {
            "protocol": "full-persona-corpus/0.2",
            "study": study.study_id,
            "holdout": freeze.freeze_sha256,
            "sources": source_snapshot,
            "exclusions": exclusion_snapshot,
            "config": limits.config_sha256,
        }
    )
