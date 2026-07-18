from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from ynoy.constants import CODEX_HARVEST_RETENTION_DAYS
from ynoy.errors import DataValidationError
from ynoy.models import (
    DataClass,
    ProtectedHoldoutFreeze,
    StudyArtifactIndex,
)
from ynoy.models.persona_harvest import (
    HarvestCheckpoint,
    HarvestLimits,
    HarvestManifest,
)
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.harvest_contract import (
    new_harvest_run_id,
    seal_harvest_manifest,
)
from ynoy.persona_study.harvest_processor import (
    Clock,
    HarvestProcessingResult,
    process_harvest_checkpoint,
)
from ynoy.util import canonical_json_bytes, utc_now

MANIFEST_PATH = "evaluator/harvest-manifest.json"
_CHECKPOINT = re.compile(r"^evaluator/harvest-checkpoint-(\d{4})\.json$")


@dataclass(frozen=True, slots=True)
class PreparedHarvest:
    manifest: HarvestManifest
    checkpoint: HarvestCheckpoint
    artifact_index: StudyArtifactIndex
    review_path: Path
    labels_path: Path
    metadata_entries_scanned: int


def prepare_harvest(
    source_root: Path,
    private_root: Path,
    source_study_id: str,
    *,
    synthetic: bool,
    limits: HarvestLimits | None = None,
    evaluation_time: datetime | None = None,
    clock: Clock = time.monotonic,
) -> PreparedHarvest:
    """Create one private, bounded harvest run tied to an existing holdout freeze."""
    now = evaluation_time or utc_now()
    store = PersonaStudyStore(private_root, real_data=not synthetic, evaluation_time=now)
    freeze = _read_freeze(store, source_study_id, synthetic)
    chosen_limits = limits or HarvestLimits()
    run_id = new_harvest_run_id()
    stable_before_ns = min(
        int((now - timedelta(minutes=5)).timestamp() * 1_000_000_000),
        freeze.boundary_session_start_ns - 1,
    )
    manifest = seal_harvest_manifest(
        run_id=run_id,
        source_study_id=source_study_id,
        freeze_sha256=freeze.freeze_sha256,
        boundary_ns=freeze.boundary_session_start_ns,
        stable_before_ns=stable_before_ns,
        limits=chosen_limits,
        created_at=now,
        expires_at=now + timedelta(days=CODEX_HARVEST_RETENTION_DAYS),
        synthetic=synthetic,
    )
    processed = process_harvest_checkpoint(source_root, manifest, clock=clock)
    payloads = _initial_payloads(manifest, processed)
    index = store.write_run(
        run_id, payloads, created_at=manifest.created_at, expires_at=manifest.expires_at
    )
    return _prepared(store, manifest, processed, index)


def resume_harvest(
    source_root: Path,
    private_root: Path,
    run_id: str,
    *,
    synthetic: bool,
    clock: Clock = time.monotonic,
) -> PreparedHarvest:
    """Append exactly one expected harvest revision or fail without advancing."""
    store = PersonaStudyStore(private_root, real_data=not synthetic)
    manifest = _read_manifest(store, run_id)
    if manifest.synthetic != synthetic:
        raise DataValidationError(
            "codex_harvest_mode_mismatch", "The harvest mode does not match its manifest."
        )
    previous = _read_latest_checkpoint(store, run_id)
    processed = process_harvest_checkpoint(source_root, manifest, previous, clock=clock)
    payloads = _revision_payloads(processed, manifest)
    index = store.append_artifacts(run_id, payloads)
    return _prepared(store, manifest, processed, index)


def _read_freeze(
    store: PersonaStudyStore, source_study_id: str, synthetic: bool
) -> ProtectedHoldoutFreeze:
    try:
        raw = store.read_artifact(source_study_id, "evaluator/protected-holdout-freeze.json")
        freeze = ProtectedHoldoutFreeze.model_validate_json(raw)
    except ValidationError as exc:
        raise DataValidationError(
            "codex_harvest_holdout_invalid", "The source holdout freeze is invalid."
        ) from exc
    expected = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS
    if freeze.source_data_class != expected:
        raise DataValidationError(
            "codex_harvest_holdout_mode_mismatch", "The source holdout mode does not match."
        )
    return freeze


def _read_manifest(store: PersonaStudyStore, run_id: str) -> HarvestManifest:
    try:
        return HarvestManifest.model_validate_json(store.read_artifact(run_id, MANIFEST_PATH))
    except ValidationError as exc:
        raise DataValidationError(
            "codex_harvest_manifest_invalid", "The private harvest manifest is invalid."
        ) from exc


def _read_latest_checkpoint(store: PersonaStudyStore, run_id: str) -> HarvestCheckpoint:
    index = store.read_index(run_id)
    matches = sorted(
        (int(match.group(1)), item.relative_path)
        for item in index.entries
        if (match := _CHECKPOINT.fullmatch(item.relative_path))
    )
    if not matches or len(matches) != matches[-1][0]:
        raise DataValidationError(
            "codex_harvest_checkpoint_chain_invalid", "The harvest checkpoint chain is incomplete."
        )
    try:
        return HarvestCheckpoint.model_validate_json(store.read_artifact(run_id, matches[-1][1]))
    except ValidationError as exc:
        raise DataValidationError(
            "codex_harvest_checkpoint_invalid", "The latest harvest checkpoint is invalid."
        ) from exc


def _initial_payloads(
    manifest: HarvestManifest, processed: HarvestProcessingResult
) -> tuple[ArtifactPayload, ...]:
    manifest_bytes = canonical_json_bytes(manifest.model_dump(mode="json"))
    manifest_payload = ArtifactPayload(
        MANIFEST_PATH,
        manifest_bytes,
        _derived_class(manifest.synthetic),
        (manifest.holdout_freeze_sha256,),
    )
    return (manifest_payload, *_revision_payloads(processed, manifest))


def _revision_payloads(
    processed: HarvestProcessingResult, manifest: HarvestManifest
) -> tuple[ArtifactPayload, ...]:
    checkpoint = processed.checkpoint
    revision = checkpoint.cursor.revision
    dependencies = processed.source_dependencies
    raw_class = DataClass.PUBLIC_SYNTHETIC if manifest.synthetic else DataClass.RAW_CORPUS
    derived_class = _derived_class(manifest.synthetic)
    checkpoint_bytes = canonical_json_bytes(checkpoint.model_dump(mode="json"))
    review_bytes = _render_review(checkpoint).encode("utf-8")
    labels_bytes = canonical_json_bytes(_label_template(checkpoint))
    _require_bounded_output(
        (checkpoint_bytes, review_bytes, labels_bytes), manifest.limits.max_artifact_bytes
    )
    return (
        ArtifactPayload(
            f"evaluator/harvest-checkpoint-{revision:04d}.json",
            checkpoint_bytes,
            raw_class,
            dependencies,
        ),
        ArtifactPayload(
            f"annotator/harvest-review-{revision:04d}.md",
            review_bytes,
            raw_class,
            dependencies,
        ),
        ArtifactPayload(
            f"annotator/harvest-labels-{revision:04d}.template.json",
            labels_bytes,
            derived_class,
            dependencies,
            "represented_user",
        ),
    )


def _prepared(
    store: PersonaStudyStore,
    manifest: HarvestManifest,
    processed: HarvestProcessingResult,
    index: StudyArtifactIndex,
) -> PreparedHarvest:
    revision = processed.checkpoint.cursor.revision
    return PreparedHarvest(
        manifest,
        processed.checkpoint,
        index,
        store.paths.artifact(manifest.run_id, f"annotator/harvest-review-{revision:04d}.md"),
        store.paths.artifact(
            manifest.run_id, f"annotator/harvest-labels-{revision:04d}.template.json"
        ),
        processed.metadata_entries_scanned,
    )


def _render_review(checkpoint: HarvestCheckpoint) -> str:
    lines = [
        "# Bounded Judgment Candidate Audit",
        "",
        "> Every focus remains unattributed and is not persona truth.",
        "> Mark only whether the focus is yours and whether it contains a real judgment.",
        "",
    ]
    for index, candidate in enumerate(checkpoint.candidates[:12], start=1):
        lines.extend(
            (f"## Candidate {index}", "", f"Signals: {', '.join(candidate.signal_tags)}", "")
        )
        for message in candidate.context:
            lines.extend((f"**Context ({message.speaker})**", "", message.content, ""))
        lines.extend(("**Focus (unattributed user turn)**", "", candidate.focus, ""))
    return "\n".join(lines)


def _label_template(checkpoint: HarvestCheckpoint) -> dict[str, object]:
    return {
        "protocol": "codex-judgment-harvest-audit/0.1",
        "run_id": checkpoint.cursor.run_id,
        "revision": checkpoint.cursor.revision,
        "instructions": (
            "Set authorship and judgment_signal for each candidate; leave uncertain blank."
        ),
        "labels": [
            {
                "candidate_id": item.candidate_id,
                "authorship": None,
                "judgment_signal": None,
                "corrected_signal_tags": [],
                "notes": None,
            }
            for item in checkpoint.candidates[:12]
        ],
    }


def _require_bounded_output(values: tuple[bytes, ...], maximum: int) -> None:
    if sum(len(content) for content in values) > maximum:
        raise DataValidationError(
            "codex_harvest_output_limit", "The private harvest output exceeds its limit."
        )


def _derived_class(synthetic: bool) -> DataClass:
    return DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
