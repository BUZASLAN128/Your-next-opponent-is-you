from __future__ import annotations

import re

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import DataClass, StudyArtifactEntry, StudyArtifactIndex
from ynoy.models.harvest_authorship import HarvestAuthorshipReceipt
from ynoy.models.persona_harvest import HarvestCheckpoint, HarvestManifest
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest import MANIFEST_PATH
from ynoy.persona_study.storage_paths import require_regular_file
from ynoy.util import sha256_bytes

_CHECKPOINT = re.compile(r"^evaluator/harvest-checkpoint-(\d{4})\.json$")


def load_manifest(
    store: PersonaStudyStore, index: StudyArtifactIndex, run_id: str
) -> HarvestManifest:
    entry = immutable_entry(index, MANIFEST_PATH)
    try:
        manifest = HarvestManifest.model_validate_json(immutable_bytes(store, run_id, entry))
    except ValidationError as exc:
        raise DataValidationError(
            "harvest_authorship_manifest_invalid", "The harvest manifest is invalid."
        ) from exc
    if manifest.run_id != run_id or index.study_id != run_id:
        raise DataValidationError(
            "harvest_authorship_run_mismatch", "The harvest run binding is invalid."
        )
    return manifest


def load_checkpoint(
    store: PersonaStudyStore,
    index: StudyArtifactIndex,
    run_id: str,
    revision: int,
) -> tuple[HarvestCheckpoint, StudyArtifactEntry]:
    require_checkpoint_chain(index)
    entry = immutable_entry(index, checkpoint_path(revision))
    try:
        value = HarvestCheckpoint.model_validate_json(immutable_bytes(store, run_id, entry))
    except ValidationError as exc:
        raise DataValidationError(
            "harvest_authorship_checkpoint_invalid",
            "The harvest checkpoint is invalid.",
        ) from exc
    return value, entry


def load_receipt(
    store: PersonaStudyStore,
    run_id: str,
    entry: StudyArtifactEntry,
) -> HarvestAuthorshipReceipt:
    try:
        return HarvestAuthorshipReceipt.model_validate_json(immutable_bytes(store, run_id, entry))
    except ValidationError as exc:
        raise DataValidationError(
            "harvest_authorship_receipt_invalid",
            "The immutable harvest authorship receipt is invalid.",
        ) from exc


def require_checkpoint_chain(index: StudyArtifactIndex) -> None:
    revisions = _checkpoint_revisions(index)
    if not revisions or revisions != list(range(1, revisions[-1] + 1)):
        raise DataValidationError(
            "harvest_authorship_checkpoint_chain_invalid",
            "The harvest checkpoint chain is incomplete.",
        )


def latest_revision(index: StudyArtifactIndex) -> int:
    require_checkpoint_chain(index)
    return max(_checkpoint_revisions(index))


def existing_receipt(index: StudyArtifactIndex, revision: int) -> StudyArtifactEntry | None:
    matches = tuple(
        entry for entry in index.entries if entry.relative_path == receipt_path(revision)
    )
    if len(matches) > 1:
        raise DataValidationError(
            "harvest_authorship_receipt_duplicate", "The authorship receipt is ambiguous."
        )
    return matches[0] if matches else None


def immutable_entry(index: StudyArtifactIndex, path: str) -> StudyArtifactEntry:
    matches = tuple(
        entry
        for entry in index.entries
        if entry.relative_path == path and entry.mutable_by == "none"
    )
    if len(matches) != 1:
        raise DataValidationError(
            "harvest_authorship_artifact_missing",
            "A required immutable harvest artifact is missing.",
        )
    return matches[0]


def immutable_bytes(store: PersonaStudyStore, run_id: str, entry: StudyArtifactEntry) -> bytes:
    path = store.paths.artifact(run_id, entry.relative_path)
    require_regular_file(path)
    content = path.read_bytes()
    if sha256_bytes(content) != entry.sha256:
        raise DataValidationError(
            "harvest_authorship_artifact_tampered",
            "A harvest authorship ancestor changed.",
        )
    return content


def derived_class(manifest: HarvestManifest) -> DataClass:
    return DataClass.PUBLIC_SYNTHETIC if manifest.synthetic else DataClass.DERIVED_IDENTITY


def checkpoint_path(revision: int) -> str:
    return f"evaluator/harvest-checkpoint-{revision:04d}.json"


def review_path(revision: int) -> str:
    return f"annotator/harvest-review-{revision:04d}.md"


def receipt_path(revision: int) -> str:
    return f"evaluator/harvest-authorship-{revision:04d}.json"


def _checkpoint_revisions(index: StudyArtifactIndex) -> list[int]:
    return sorted(
        int(match.group(1))
        for entry in index.entries
        if (match := _CHECKPOINT.fullmatch(entry.relative_path))
    )
