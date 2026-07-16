from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from ynoy.constants import PERSONA_STUDY_RETENTION_DAYS
from ynoy.errors import DataValidationError
from ynoy.models import (
    DataClass,
    DeletionProofReceipt,
    PersonaStudyManifest,
    ProtectedHoldoutFreeze,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.deletion import prove_disposable_deletion
from ynoy.persona_study.render import label_template, render_review_markdown
from ynoy.persona_study.retention import ExpiryPurgeResult
from ynoy.persona_study.source import StudySourceSample, load_protected_study_source
from ynoy.persona_study.windows import PreparedWindows, prepare_windows
from ynoy.util import canonical_json_bytes, canonical_sha256, utc_now

_BASELINES = (
    "zero_abstain",
    "low_recent3",
    "history_frequency",
    "history_lexical",
    "history_declared",
    "history_structured",
)
_PRIMARY_METRICS = (
    "paired_decision_loss",
    "selective_accuracy",
    "coverage",
    "scope_validity",
    "provenance_completeness",
)
_THRESHOLDS: dict[str, float | int] = {
    "attribution_repeat_agreement": 8,
    "adoption_repeat_agreement": 8,
    "decision_repeat_agreement": 6,
    "target_layer_repeat_agreement": 6,
    "fatal_privacy_errors": 0,
    "minimum_loss_improvement": 0.10,
}


@dataclass(frozen=True, slots=True)
class PreparedPersonaStudy:
    manifest: PersonaStudyManifest
    artifact_index: StudyArtifactIndex
    review_path: Path
    labels_path: Path
    expired_artifacts_purged: int
    expired_tombstones_purged: int


def prepare_persona_study(
    source_root: Path,
    private_root: Path,
    *,
    synthetic: bool,
    evaluation_time: datetime | None = None,
) -> PreparedPersonaStudy:
    now = evaluation_time or utc_now()
    expires_at = now + timedelta(days=PERSONA_STUDY_RETENTION_DAYS)
    store, purged = _open_store(private_root, synthetic, now)
    if purged.failed_count:
        raise DataValidationError(
            "persona_study_expiry_purge_incomplete",
            "One or more private study runs could not be checked or expired safely.",
        )
    source, holdout = load_protected_study_source(
        source_root, synthetic=synthetic, evaluation_time=now
    )
    prepared = prepare_windows(source.events, source.source_snapshot_sha256)
    source_receipt = _source_receipt(source, holdout)
    del source
    replay_source, replay_holdout = load_protected_study_source(
        source_root, synthetic=synthetic, evaluation_time=now
    )
    replay = prepare_windows(replay_source.events, replay_source.source_snapshot_sha256)
    _verify_replay(
        prepared,
        replay,
        source_receipt,
        _source_receipt(replay_source, replay_holdout),
    )
    source = replay_source
    del replay_source, replay_holdout, replay
    proof = prove_disposable_deletion(
        store, prepared.windows[0], created_at=now, expires_at=expires_at
    )
    manifest = _build_manifest(
        source, prepared, holdout.freeze_sha256, proof.proof_id, now, expires_at
    )
    payloads = _study_payloads(prepared, manifest, holdout, proof, synthetic)
    index = store.write_run(prepared.study_id, payloads, created_at=now, expires_at=expires_at)
    annotator_root = private_root.resolve() / "persona-study-annotator" / prepared.study_id
    return PreparedPersonaStudy(
        manifest,
        index,
        annotator_root / "review.md",
        annotator_root / "labels.template.json",
        purged.deleted_artifact_count,
        purged.deleted_tombstone_count,
    )


def _open_store(
    private_root: Path, synthetic: bool, now: datetime
) -> tuple[PersonaStudyStore, ExpiryPurgeResult]:
    store = PersonaStudyStore(private_root, real_data=not synthetic, evaluation_time=now)
    return store, store.purge_expired(now)


def _verify_replay(
    first: PreparedWindows,
    second: PreparedWindows,
    first_source: tuple[object, ...],
    second_source: tuple[object, ...],
) -> None:
    receipt = (
        first.study_id,
        first.selection_sha256,
        first.blind_map_sha256,
        tuple(item.window_sha256 for item in first.windows),
    )
    replay = (
        second.study_id,
        second.selection_sha256,
        second.blind_map_sha256,
        tuple(item.window_sha256 for item in second.windows),
    )
    if first_source != second_source or receipt != replay:
        raise DataValidationError(
            "persona_study_replay_mismatch", "Deterministic persona-study replay did not match."
        )


def _source_receipt(
    source: StudySourceSample, holdout: ProtectedHoldoutFreeze
) -> tuple[object, ...]:
    return (
        source.source_snapshot_sha256,
        source.selected_file_count,
        source.selected_input_bytes,
        source.scanned_record_count,
        len(source.events),
        source.selected_file_receipts,
        source.selected_max_session_start_ns,
        holdout.freeze_sha256,
    )


def _build_manifest(
    source: StudySourceSample,
    prepared: PreparedWindows,
    holdout_freeze_sha256: str,
    proof_id: str,
    created_at: datetime,
    expires_at: datetime,
) -> PersonaStudyManifest:
    payload = {
        "study_id": prepared.study_id,
        "source_snapshot_sha256": source.source_snapshot_sha256,
        "selection_sha256": prepared.selection_sha256,
        "blind_map_sha256": prepared.blind_map_sha256,
        "cutoff": prepared.cutoff,
        "created_at": created_at,
        "expires_at": expires_at,
        "selected_file_count": source.selected_file_count,
        "selected_input_bytes": source.selected_input_bytes,
        "scanned_record_count": source.scanned_record_count,
        "normalized_event_count": len(source.events),
        "annotation_development_count": prepared.annotation_development_count,
        "annotation_reserved_count": prepared.annotation_reserved_count,
        "dependency_component_count": prepared.dependency_component_count,
        "baseline_names": _BASELINES,
        "primary_metrics": _PRIMARY_METRICS,
        "thresholds": _THRESHOLDS,
        "deletion_proof_id": proof_id,
        "protected_holdout_freeze_sha256": holdout_freeze_sha256,
        "source_data_class": source.events[0].data_class,
    }
    draft = cast(Any, PersonaStudyManifest).model_construct(**payload, manifest_sha256="0" * 64)
    receipt = canonical_sha256(draft.model_dump(mode="json", exclude={"manifest_sha256"}))
    return PersonaStudyManifest.model_validate({**payload, "manifest_sha256": receipt})


def _study_payloads(
    prepared: PreparedWindows,
    manifest: PersonaStudyManifest,
    holdout: ProtectedHoldoutFreeze,
    proof: DeletionProofReceipt,
    synthetic: bool,
) -> tuple[ArtifactPayload, ...]:
    dependencies = tuple(
        sorted(
            {source for window in prepared.windows for source in window.source_dependencies}
            | {item.source_receipt for item in holdout.sources}
        )
    )
    raw_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS
    derived_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
    values = _artifact_values(prepared, manifest, holdout, proof, raw_class, derived_class)
    return tuple(
        ArtifactPayload(
            name,
            _encode(value),
            data_class,
            dependencies,
            "represented_user" if name == "annotator/labels.template.json" else "none",
        )
        for name, value, data_class in values
    )


def _artifact_values(
    prepared: PreparedWindows,
    manifest: PersonaStudyManifest,
    holdout: ProtectedHoldoutFreeze,
    proof: DeletionProofReceipt,
    raw_class: DataClass,
    derived_class: DataClass,
) -> tuple[tuple[str, object | str, DataClass], ...]:
    values: tuple[tuple[str, object | str, DataClass], ...] = (
        ("evaluator/manifest.json", manifest.model_dump(mode="json"), derived_class),
        (
            "evaluator/protected-holdout-freeze.json",
            holdout.model_dump(mode="json"),
            derived_class,
        ),
        (
            "evaluator/windows.json",
            [item.model_dump(mode="json") for item in prepared.windows],
            raw_class,
        ),
        (
            "annotator/presentations.json",
            [item.model_dump(mode="json") for item in prepared.presentations],
            raw_class,
        ),
        (
            "evaluator/blind-map.json",
            [item.model_dump(mode="json") for item in prepared.blind_map],
            derived_class,
        ),
        (
            "annotator/labels.template.json",
            label_template(prepared.study_id, prepared.presentations),
            derived_class,
        ),
        ("annotator/review.md", render_review_markdown(prepared.presentations), raw_class),
        ("evaluator/deletion-proof.json", proof, derived_class),
    )
    return values


def _encode(value: object | str) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return canonical_json_bytes(value)
