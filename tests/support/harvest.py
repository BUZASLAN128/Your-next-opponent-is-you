from __future__ import annotations

import io
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from ynoy.corpus.codex_normalizer import normalize_codex_record
from ynoy.corpus.codex_normalizer_types import CodexFileBinding, CodexParserState
from ynoy.corpus.codex_raw_records import iter_jsonl_records
from ynoy.models import DataClass, NormalizedCodexEvent
from ynoy.models.persona_harvest import HarvestCandidate, HarvestManifest
from ynoy.persona_study.harvest_contract import seal_harvest_candidate
from ynoy.persona_study.harvest_signals import evaluate_harvest_event


def normalized_event(role: str, content: str) -> NormalizedCodexEvent:
    records: list[object] = [
        {"type": "session_meta", "payload": {"id": "synthetic-harvest-thread"}},
        {
            "type": "response_item",
            "timestamp": "2026-01-02T03:04:05+00:00",
            "payload": {
                "type": "message",
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            },
        },
    ]
    encoded = b"".join(json.dumps(item).encode() + b"\n" for item in records)
    state = CodexParserState()
    binding = CodexFileBinding(
        snapshot_id=UUID(int=31),
        source_key="1" * 64,
        blob_sha256="2" * 64,
        data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )
    events = [
        normalize_codex_record(raw, state, binding)
        for raw in iter_jsonl_records(io.BytesIO(encoded))
    ]
    return events[1]


def sealed_candidate(
    event: NormalizedCodexEvent, manifest: HarvestManifest, receipt: str, score: int
) -> HarvestCandidate:
    result = evaluate_harvest_event(event, manifest.limits)
    return seal_harvest_candidate(
        event,
        partition="sessions",
        source_receipt=receipt,
        context=(),
        tags=result.tags,
        score=score,
        selector_config_sha256=manifest.selector_config_sha256,
    )


def write_rollout(root: Path, name: str, messages: Iterable[tuple[str, str]]) -> Path:
    path = root / "sessions" / "2026" / "01" / "02" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[object] = [
        {
            "type": "session_meta",
            "payload": {"id": f"thread-{name}"},
        }
    ]
    for role, text in messages:
        records.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    timestamp = int(datetime(2026, 1, 2, tzinfo=UTC).timestamp() * 1_000_000_000)
    import os

    os.utime(path, ns=(timestamp, timestamp))
    return path
