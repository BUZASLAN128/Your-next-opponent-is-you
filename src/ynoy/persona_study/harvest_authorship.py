from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactEntry, StudyArtifactIndex
from ynoy.models.harvest_authorship import (
    HarvestAuthorshipReceipt,
    HarvestAuthorshipSubmission,
    seal_harvest_authorship_receipt,
)
from ynoy.models.persona_harvest import HarvestCheckpoint, HarvestManifest
from ynoy.persona_study.artifact_contract import ArtifactPayload
from ynoy.persona_study.artifact_mutations import append_artifacts_locked
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest import render_harvest_review
from ynoy.persona_study.harvest_authorship_artifacts import (
    derived_class,
    existing_receipt,
    immutable_entry,
    latest_revision,
    load_checkpoint,
    load_manifest,
    load_receipt,
    receipt_path,
    review_path,
)
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes


@dataclass(frozen=True, slots=True)
class HarvestAuthorshipResult:
    receipt: HarvestAuthorshipReceipt
    artifact_index: StudyArtifactIndex


def current_all_self_submission(
    store: PersonaStudyStore,
    run_id: str,
    *,
    expected_revision: int,
    expected_checkpoint_sha256: str,
) -> HarvestAuthorshipSubmission:
    """Build an authorship-only submission for the exact current review surface."""
    index = store.read_index(run_id)
    manifest = load_manifest(store, index, run_id)
    checkpoint, _ = load_checkpoint(store, index, run_id, expected_revision)
    if (
        expected_revision != latest_revision(index)
        or checkpoint.checkpoint_sha256 != expected_checkpoint_sha256
    ):
        raise DataValidationError(
            "harvest_authorship_expected_head_mismatch",
            "The requested harvest review is not the current checkpoint head.",
        )
    candidates = checkpoint.candidates[:12]
    return HarvestAuthorshipSubmission(
        source_study_id=manifest.source_study_id,
        run_id=run_id,
        revision=expected_revision,
        checkpoint_sha256=expected_checkpoint_sha256,
        candidate_ids=tuple(item.candidate_id for item in candidates),
        authorships=tuple("self" for _ in candidates),
    )


def submit_harvest_authorship(
    store: PersonaStudyStore, submission: HarvestAuthorshipSubmission
) -> HarvestAuthorshipResult:
    """Seal one exact authorship confirmation without granting semantic authority."""
    value = _validated_submission(submission)
    store.read_index(value.run_id)
    with store.study_lock(value.run_id):
        index = store._read_index_unchecked(value.run_id)
        existing = existing_receipt(index, value.revision)
        if existing is not None:
            return _replay(store, index, value, existing)
        if value.revision != latest_revision(index):
            raise DataValidationError(
                "harvest_authorship_stale_revision",
                "A first authorship receipt must target the current harvest revision.",
            )
        return _seal_locked(store, index, value)


def _seal_locked(
    store: PersonaStudyStore,
    index: StudyArtifactIndex,
    submission: HarvestAuthorshipSubmission,
) -> HarvestAuthorshipResult:
    manifest = load_manifest(store, index, submission.run_id)
    checkpoint, checkpoint_entry = load_checkpoint(
        store, index, submission.run_id, submission.revision
    )
    review_entry = immutable_entry(index, review_path(submission.revision))
    _validate_submission(submission, manifest, checkpoint, review_entry)
    dependencies = tuple(
        sorted({*checkpoint_entry.source_dependencies, manifest.holdout_freeze_sha256})
    )
    receipt = _receipt(index, submission, manifest, checkpoint, review_entry, dependencies)
    payload = ArtifactPayload(
        receipt_path(submission.revision),
        canonical_json_bytes(receipt.model_dump(mode="json")),
        derived_class(manifest),
        dependencies,
    )
    updated = append_artifacts_locked(store, submission.run_id, (payload,))
    return HarvestAuthorshipResult(receipt, updated)


def _replay(
    store: PersonaStudyStore,
    index: StudyArtifactIndex,
    submission: HarvestAuthorshipSubmission,
    entry: StudyArtifactEntry,
) -> HarvestAuthorshipResult:
    receipt = load_receipt(store, submission.run_id, entry)
    manifest = load_manifest(store, index, submission.run_id)
    checkpoint, _ = load_checkpoint(store, index, submission.run_id, submission.revision)
    review = immutable_entry(index, review_path(submission.revision))
    _validate_submission(submission, manifest, checkpoint, review)
    expected = _receipt(
        index,
        submission,
        manifest,
        checkpoint,
        review,
        tuple(sorted({*entry.source_dependencies})),
        prior_index_sha256=receipt.prior_index_sha256,
    )
    if receipt != expected:
        raise DataValidationError(
            "harvest_authorship_receipt_conflict",
            "The existing authorship receipt does not match this exact retry.",
        )
    return HarvestAuthorshipResult(receipt, index)


def _validate_submission(
    submission: HarvestAuthorshipSubmission,
    manifest: HarvestManifest,
    checkpoint: HarvestCheckpoint,
    review: StudyArtifactEntry,
) -> None:
    candidates = checkpoint.candidates[:12]
    expected_ids = tuple(item.candidate_id for item in candidates)
    real_count_valid = manifest.synthetic or len(candidates) == 12
    if (
        submission.run_id != manifest.run_id
        or submission.source_study_id != manifest.source_study_id
        or checkpoint.cursor.run_id != manifest.run_id
        or checkpoint.cursor.source_study_id != manifest.source_study_id
        or checkpoint.cursor.holdout_freeze_sha256 != manifest.holdout_freeze_sha256
        or checkpoint.cursor.selector_config_sha256 != manifest.selector_config_sha256
        or checkpoint.cursor.stable_before_ns != manifest.stable_before_ns
        or submission.revision != checkpoint.cursor.revision
        or submission.checkpoint_sha256 != checkpoint.checkpoint_sha256
        or review.sha256 != sha256_bytes(render_harvest_review(checkpoint).encode("utf-8"))
        or submission.candidate_ids != expected_ids
        or submission.authorships != ("self",) * len(expected_ids)
        or not real_count_valid
        or checkpoint.status not in {"audit_ready", "complete"}
    ):
        raise DataValidationError(
            "harvest_authorship_contract_mismatch",
            "Authorship confirmation does not match the exact review package.",
        )


def _receipt(
    index: StudyArtifactIndex,
    submission: HarvestAuthorshipSubmission,
    manifest: HarvestManifest,
    checkpoint: HarvestCheckpoint,
    review_entry: StudyArtifactEntry,
    dependencies: tuple[str, ...],
    *,
    prior_index_sha256: str | None = None,
) -> HarvestAuthorshipReceipt:
    candidates = checkpoint.candidates[:12]
    candidate_ids = tuple(item.candidate_id for item in candidates)
    candidate_sha256s = tuple(item.candidate_sha256 for item in candidates)
    authorships = tuple("self" for _ in candidates)
    return seal_harvest_authorship_receipt(
        source_study_id=manifest.source_study_id,
        run_id=manifest.run_id,
        revision=checkpoint.cursor.revision,
        manifest_sha256=manifest.manifest_sha256,
        holdout_freeze_sha256=manifest.holdout_freeze_sha256,
        selector_config_sha256=manifest.selector_config_sha256,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        review_sha256=review_entry.sha256,
        prior_index_sha256=prior_index_sha256 or index.index_sha256,
        source_dependencies_sha256=canonical_sha256(dependencies),
        candidate_ids=candidate_ids,
        candidate_sha256s=candidate_sha256s,
        authorships=authorships,
        candidate_set_sha256=canonical_sha256(
            {
                "candidate_ids": candidate_ids,
                "candidate_sha256s": candidate_sha256s,
                "authorships": authorships,
            }
        ),
        submission_sha256=canonical_sha256(submission.model_dump(mode="json")),
    )


def _validated_submission(value: HarvestAuthorshipSubmission) -> HarvestAuthorshipSubmission:
    try:
        return HarvestAuthorshipSubmission.model_validate(value.model_dump(mode="python"))
    except ValidationError as exc:
        raise DataValidationError(
            "harvest_authorship_submission_invalid",
            "The harvest authorship submission is invalid.",
        ) from exc
