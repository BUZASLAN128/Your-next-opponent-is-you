from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from ynoy.corpus.codex import SYNTHETIC_MARKER


def synthetic_codex_study_root(tmp_path: Path) -> tuple[Path, tuple[str, ...]]:
    root = tmp_path / "synthetic-codex"
    (root / "sessions").mkdir(parents=True)
    (root / ".ynoy-synthetic-codex-fixture").write_bytes(SYNTHETIC_MARKER)
    sentinels: list[str] = []
    for index in range(40):
        observed = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
        identity = UUID(int=index + 1)
        filename = f"rollout-{observed:%Y-%m-%d}T03-04-05-{identity}.jsonl"
        path = root / "sessions" / f"{observed:%Y}" / f"{observed:%m}" / f"{observed:%d}" / filename
        path.parent.mkdir(parents=True)
        context = f"PRIVATE_CONTEXT_{index:02d}"
        focus = (
            f"persona yanlis olmasin? challenge-{index:02d}"
            if index < 12
            else f"Persona preference item {index:02d}"
        )
        sentinels.extend((context, focus, f"raw-private-thread-{index:02d}", filename))
        session_payload = {"id": f"raw-private-thread-{index:02d}"}
        if index % 2:
            session_payload["parent_thread_id"] = f"raw-private-thread-{index - 1:02d}"
        records = [
            {"type": "session_meta", "payload": session_payload},
            _message("assistant", context, observed, minute=0),
            _message("user", focus, observed, minute=1),
        ]
        path.write_text(
            "".join(f"{json.dumps(item, separators=(',', ':'))}\n" for item in records),
            encoding="utf-8",
        )
        observed_ns = int(observed.timestamp() * 1_000_000_000)
        os.utime(path, ns=(observed_ns, observed_ns))
    return root, tuple(sentinels)


def _message(role: str, text: str, observed: datetime, *, minute: int) -> dict[str, object]:
    timestamp = observed.replace(hour=3, minute=minute).isoformat()
    return {
        "type": "response_item",
        "timestamp": timestamp,
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": text}],
        },
    }
