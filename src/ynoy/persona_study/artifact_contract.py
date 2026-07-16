from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from ynoy.errors import DataValidationError
from ynoy.models import DataClass, StudyArtifactEntry, StudyArtifactIndex
from ynoy.util import canonical_sha256, sha256_bytes


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    relative_path: str
    content: bytes
    data_class: DataClass
    source_dependencies: tuple[str, ...]
    mutable_by: Literal["none", "represented_user"] = "none"


def artifact_entry(payload: ArtifactPayload) -> StudyArtifactEntry:
    return StudyArtifactEntry(
        relative_path=payload.relative_path,
        sha256=sha256_bytes(payload.content),
        data_class=payload.data_class,
        source_dependencies=payload.source_dependencies,
        mutable_by=payload.mutable_by,
    )


def artifact_index(
    study_id: str,
    created_at: datetime,
    expires_at: datetime,
    entries: tuple[StudyArtifactEntry, ...],
) -> StudyArtifactIndex:
    payload = {
        "study_id": study_id,
        "created_at": created_at,
        "expires_at": expires_at,
        "entries": entries,
    }
    draft = cast(Any, StudyArtifactIndex).model_construct(**payload, index_sha256="0" * 64)
    receipt = canonical_sha256(draft.model_dump(mode="json", exclude={"index_sha256"}))
    return StudyArtifactIndex.model_validate({**payload, "index_sha256": receipt})


def mutable_entry(index: StudyArtifactIndex, relative: str) -> StudyArtifactEntry:
    matches = tuple(item for item in index.entries if item.relative_path == relative)
    if len(matches) != 1 or matches[0].mutable_by != "represented_user":
        raise DataValidationError(
            "persona_study_mutable_draft_required",
            "The requested represented-user draft is unavailable or already sealed.",
        )
    return matches[0]


def require_unique_payloads(payloads: tuple[ArtifactPayload, ...]) -> None:
    paths = tuple(item.relative_path for item in payloads)
    if len(paths) != len(set(paths)):
        raise DataValidationError(
            "persona_study_artifact_duplicate", "Study artifact paths must be unique."
        )
