from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from ynoy.models import (
    DataClass,
    NormalizedCodexEvent,
)
from ynoy.models.persona_harvest import (
    HarvestCandidate,
    HarvestCheckpoint,
    HarvestContextMessage,
    HarvestCursor,
    HarvestFileCursor,
    HarvestLimits,
    HarvestManifest,
    HarvestSignal,
    HarvestStatus,
)
from ynoy.util import canonical_sha256, new_id, sha256_text


def new_harvest_run_id() -> str:
    return canonical_sha256({"protocol": "codex-judgment-harvest/0.1", "nonce": new_id()})


def seal_harvest_manifest(
    *,
    run_id: str,
    source_study_id: str,
    freeze_sha256: str,
    boundary_ns: int,
    stable_before_ns: int,
    limits: HarvestLimits,
    created_at: datetime,
    expires_at: datetime,
    synthetic: bool,
) -> HarvestManifest:
    payload = {
        "run_id": run_id,
        "source_study_id": source_study_id,
        "holdout_freeze_sha256": freeze_sha256,
        "holdout_boundary_session_start_ns": boundary_ns,
        "stable_before_ns": stable_before_ns,
        "selector_config_sha256": limits.config_sha256,
        "limits": limits,
        "created_at": created_at,
        "expires_at": expires_at,
        "source_data_class": DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS,
        "synthetic": synthetic,
    }
    draft = cast(Any, HarvestManifest).model_construct(**payload, manifest_sha256="0" * 64)
    return HarvestManifest.model_validate(
        {
            **payload,
            "manifest_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"manifest_sha256"})
            ),
        }
    )


def seal_harvest_candidate(
    event: NormalizedCodexEvent,
    *,
    partition: str,
    source_receipt: str,
    context: tuple[HarvestContextMessage, ...],
    tags: tuple[HarvestSignal, ...],
    score: int,
    selector_config_sha256: str,
) -> HarvestCandidate:
    assert event.content is not None
    assert event.content_sha256 is not None
    assert event.conversation_key is not None
    assert event.event_time is not None
    candidate_id = sha256_text(
        f"{selector_config_sha256}:{event.source_key}:{event.byte_start}:{event.record_sha256}"
    )
    payload = {
        "candidate_id": candidate_id,
        "partition": partition,
        "session_month": event.event_time.strftime("%Y-%m"),
        "source_key": event.source_key,
        "source_receipt": source_receipt,
        "blob_sha256": event.blob_sha256,
        "byte_start": event.byte_start,
        "byte_length": event.byte_length,
        "record_sha256": event.record_sha256,
        "conversation_key": event.conversation_key,
        "turn_key": event.turn_key,
        "event_time": event.event_time,
        "signal_score": score,
        "signal_tags": tags,
        "context": context,
        "focus": event.content,
        "focus_sha256": event.content_sha256,
    }
    draft = cast(Any, HarvestCandidate).model_construct(**payload, candidate_sha256="0" * 64)
    return HarvestCandidate.model_validate(
        {
            **payload,
            "candidate_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"candidate_sha256"})
            ),
        }
    )


def seal_harvest_cursor(
    *,
    run_id: str,
    source_study_id: str,
    freeze_sha256: str,
    stable_before_ns: int,
    selector_config_sha256: str,
    revision: int,
    last_file: HarvestFileCursor | None,
    complete: bool,
) -> HarvestCursor:
    payload = {
        "run_id": run_id,
        "source_study_id": source_study_id,
        "holdout_freeze_sha256": freeze_sha256,
        "stable_before_ns": stable_before_ns,
        "selector_config_sha256": selector_config_sha256,
        "revision": revision,
        "last_file": last_file,
        "status": "complete" if complete else "partial",
    }
    draft = cast(Any, HarvestCursor).model_construct(**payload, cursor_sha256="0" * 64)
    return HarvestCursor.model_validate(
        {
            **payload,
            "cursor_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"cursor_sha256"})
            ),
        }
    )


def seal_harvest_checkpoint(
    *,
    cursor: HarvestCursor,
    candidates: tuple[HarvestCandidate, ...],
    exclusion_counts: dict[str, int],
    input_bytes: int,
    record_count: int,
    event_count: int,
    file_count: int,
    status: HarvestStatus,
) -> HarvestCheckpoint:
    payload = {
        "cursor": cursor,
        "candidates": candidates,
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "checkpoint_input_bytes": input_bytes,
        "checkpoint_record_count": record_count,
        "checkpoint_event_count": event_count,
        "checkpoint_file_count": file_count,
        "status": status,
    }
    draft = cast(Any, HarvestCheckpoint).model_construct(**payload, checkpoint_sha256="0" * 64)
    return HarvestCheckpoint.model_validate(
        {
            **payload,
            "checkpoint_sha256": canonical_sha256(
                draft.model_dump(mode="json", exclude={"checkpoint_sha256"})
            ),
        }
    )
