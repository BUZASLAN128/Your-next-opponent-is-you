from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from support.persona_study import synthetic_codex_study_root
from ynoy.persona_study.prepare import PreparedPersonaStudy, prepare_persona_study
from ynoy.util import utc_now


def prepared_full_persona_source(tmp_path: Path) -> tuple[Path, Path, PreparedPersonaStudy]:
    """Create a synthetic source plus the existing protected study it binds to."""
    source_root, _ = synthetic_codex_study_root(tmp_path)
    private_root = tmp_path / "private"
    prepared = prepare_persona_study(
        source_root,
        private_root,
        synthetic=True,
        evaluation_time=utc_now(),
    )
    return source_root, private_root, prepared


def add_large_canonical_file(source_root: Path, *, size: int = 4 * 1024 * 1024 + 257) -> Path:
    """Add a pre-holdout canonical file whose content exceeds the old 4 MiB limit."""
    path = (
        source_root
        / "sessions"
        / "2025"
        / "12"
        / "31"
        / ("rollout-2025-12-31T03-04-05-ffffffff-ffff-ffff-ffff-ffffffffffff.jsonl")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"type": "session_meta", "payload": {"id": "synthetic-large-session"}}
    prefix = (json.dumps(metadata, separators=(",", ":")) + "\n").encode()
    path.write_bytes(prefix + b"x" * max(0, size - len(prefix)) + b"\n")
    stable_ns = int(datetime(2025, 12, 31, 3, 4, 5, tzinfo=UTC).timestamp() * 1_000_000_000)
    os.utime(path, ns=(stable_ns, stable_ns))
    return path


def canonical_file(source_root: Path, index: int = 0) -> Path:
    identity = UUID(int=index + 1)
    return (
        source_root
        / "sessions"
        / "2026"
        / "01"
        / f"{index + 1:02d}"
        / (f"rollout-2026-01-{index + 1:02d}T03-04-05-{identity}.jsonl")
    )
