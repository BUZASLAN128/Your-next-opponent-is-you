# ruff: noqa: RUF001 -- Turkish judgment fixture mirrors selector vocabulary.

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from support.persona_study import synthetic_codex_study_root
from ynoy.models import StudyArtifactIndex
from ynoy.models.persona_harvest import HarvestLimits
from ynoy.persona_study.harvest import PreparedHarvest, prepare_harvest
from ynoy.persona_study.harvest_authorship import HarvestAuthorshipSubmission
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes


def prepare_authorship_fixture(tmp_path: Path) -> tuple[Path, Path, PreparedHarvest, datetime]:
    source, _ = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    now = datetime(2026, 7, 18, tzinfo=UTC)
    study = prepare_persona_study(source, private, synthetic=True, evaluation_time=now)
    _seed_twelve_judgment_focuses(source)
    prepared = prepare_harvest(
        source,
        private,
        study.manifest.study_id,
        synthetic=True,
        limits=HarvestLimits(
            max_files=12,
            max_total_input_bytes=20_000,
            max_file_bytes=10_000,
            max_line_bytes=8_000,
            max_records=1_000,
            max_events=1_000,
            max_entries=256,
        ),
        evaluation_time=now,
    )
    return source, private, prepared, now


def _seed_twelve_judgment_focuses(source: Path) -> None:
    paths = sorted((source / "sessions").rglob("*.jsonl"))
    for index, path in enumerate(paths):
        stat = path.stat()
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for record in records:
            if record.get("type") == "session_meta":
                payload = record.setdefault("payload", {})
                payload["id"] = f"authorship-thread-{index}"
                payload.pop("parent_thread_id", None)
                continue
            payload = record.get("payload", {})
            if payload.get("role") in {"user", "assistant"}:
                minute = 1 if payload["role"] == "user" else 0
                record["timestamp"] = f"2026-{index % 3 + 1:02d}-01T03:{minute:02d}:05+00:00"
            if payload.get("role") == "user":
                payload["content"] = [
                    {"type": "input_text", "text": f"Bunu onaylıyorum, test et candidate-{index}."}
                ]
        path.write_text(
            "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
            encoding="utf-8",
        )
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def authorship_submission(
    prepared: PreparedHarvest,
    *,
    source_study_id: str | None = None,
    run_id: str | None = None,
    revision: int | None = None,
    checkpoint_sha256: str | None = None,
    candidate_ids: tuple[str, ...] | None = None,
    authorships: tuple[str, ...] | None = None,
) -> HarvestAuthorshipSubmission:
    ids = candidate_ids or tuple(item.candidate_id for item in prepared.checkpoint.candidates[:12])
    return HarvestAuthorshipSubmission(
        source_study_id=source_study_id or prepared.manifest.source_study_id,
        run_id=run_id or prepared.manifest.run_id,
        revision=revision or prepared.checkpoint.cursor.revision,
        checkpoint_sha256=checkpoint_sha256 or prepared.checkpoint.checkpoint_sha256,
        candidate_ids=ids,
        authorships=authorships or tuple("self" for _ in ids),
    )


def replace_indexed_artifact(
    store: object, run_id: str, relative_path: str, content: bytes
) -> None:
    index_path = store.paths.index(run_id)
    index = StudyArtifactIndex.model_validate_json(index_path.read_bytes())
    store.paths.artifact(run_id, relative_path).write_bytes(content)
    entries = tuple(
        entry.model_copy(update={"sha256": sha256_bytes(content)})
        if entry.relative_path == relative_path
        else entry
        for entry in index.entries
    )
    payload = index.model_dump(mode="json", exclude={"index_sha256"})
    payload["entries"] = [entry.model_dump(mode="json") for entry in entries]
    updated = StudyArtifactIndex.model_validate(
        {**payload, "index_sha256": canonical_sha256(payload)}
    )
    index_path.write_bytes(canonical_json_bytes(updated.model_dump(mode="json")))
