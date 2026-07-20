from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Never

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.reaction_contracts import CompactReactionEvent
from ynoy.models.full_persona import EvidenceRole, FullCorpusEvidence, FullCorpusManifest
from ynoy.models.full_persona_source import FullCorpusSource
from ynoy.models.persona_reaction_benchmark import REACTION_SIGNALS

_MAX_ELIGIBLE_EVENTS = 8_192
_MAX_CONTEXT_BYTES_PER_EVENT = 8 * 1024
_MAX_COMPACT_BYTES = 128 * 1024**2
_MAX_RESPONSE_EXCERPT_CHARS = 768


def compact_reaction_events(
    evidence: Iterable[FullCorpusEvidence],
    sources: dict[str, FullCorpusSource],
    manifest: FullCorpusManifest,
) -> tuple[CompactReactionEvent, ...]:
    result: list[CompactReactionEvent] = []
    evidence_ids: set[str] = set()
    compact_bytes = 0
    try:
        for raw in evidence:
            item = FullCorpusEvidence.model_validate(raw.model_dump(mode="json"))
            source = sources.get(item.source_key)
            if source is None or item.source_receipt != source.source_receipt:
                _evidence_error("reaction evidence is not bound to its frozen source manifest")
            _validate_source_binding(item, source, manifest)
            if not _eligible(item):
                continue
            if item.evidence_id in evidence_ids:
                _evidence_error("reaction evidence identifiers repeat")
            compact = _compact(item, source)
            compact_bytes += _event_bytes(compact)
            if compact_bytes > _MAX_COMPACT_BYTES:
                _evidence_error("reaction compact evidence exceeded its byte cap")
            result.append(compact)
            evidence_ids.add(item.evidence_id)
            if len(result) > _MAX_ELIGIBLE_EVENTS:
                _evidence_error("reaction eligible evidence exceeded its bounded event cap")
    except (AttributeError, TypeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_evidence_invalid", "Reaction evidence stream is invalid."
        ) from exc
    return tuple(result)


def _validate_source_binding(
    item: FullCorpusEvidence,
    source: FullCorpusSource,
    manifest: FullCorpusManifest,
) -> None:
    boundary = datetime.fromtimestamp(
        manifest.holdout_boundary_session_start_ns / 1_000_000_000, tz=UTC
    )
    aware = item.event_time.tzinfo is not None and item.event_time.utcoffset() is not None
    context_bytes = sum(len(value.content.encode("utf-8")) for value in item.context)
    invalid = (
        item.blob_sha256 != source.blob_sha256
        or item.byte_start + item.byte_length > source.file_bytes
        or item.byte_length > manifest.limits.max_line_bytes
        or len(item.content.encode("utf-8")) > manifest.limits.max_evidence_bytes
        or len(item.context) > manifest.limits.max_context_messages
        or source.session_start_ns >= manifest.holdout_boundary_session_start_ns
        or not aware
        or (aware and item.event_time >= boundary)
        or context_bytes > _MAX_CONTEXT_BYTES_PER_EVENT
    )
    if invalid:
        _evidence_error("reaction evidence violates its frozen source or context boundary")


def _eligible(item: FullCorpusEvidence) -> bool:
    return bool(
        item.role in {EvidenceRole.DIRECT, EvidenceRole.PROJECT}
        and item.time_basis == "event"
        and item.context
        and item.content.strip()
        and any(signal in item.signal_tags for signal in REACTION_SIGNALS)
    )


def _compact(item: FullCorpusEvidence, source: FullCorpusSource) -> CompactReactionEvent:
    signal = next(signal for signal in REACTION_SIGNALS if signal in item.signal_tags)
    return CompactReactionEvent(
        evidence_id=item.evidence_id,
        evidence_sha256=item.evidence_sha256,
        event_time=item.event_time,
        source_key=item.source_key,
        source_receipt=item.source_receipt,
        conversation_key=item.conversation_key,
        lineage_component_receipt=source.lineage_component_receipt,
        context=item.context,
        content_excerpt=item.content[:_MAX_RESPONSE_EXCERPT_CHARS].strip(),
        content_sha256=item.content_sha256,
        signal=signal,
    )


def _event_bytes(item: CompactReactionEvent) -> int:
    return len(item.content_excerpt.encode("utf-8")) + sum(
        len(value.content.encode("utf-8")) for value in item.context
    )


def _evidence_error(reason: str) -> Never:
    raise DataValidationError("reaction_evidence_invalid", reason)
