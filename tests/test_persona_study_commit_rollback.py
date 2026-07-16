from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.errors import DataValidationError
from ynoy.models import StudyArtifactIndex
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.label_contract import (
    INITIAL_LABELS_PATH,
    INITIAL_RECEIPT_PATH,
    LABEL_PATH,
    SEAL_RECEIPT_PATH,
    SEALED_LABELS_PATH,
)
from ynoy.persona_study.label_submission import submit_persona_labels
from ynoy.persona_study.prepare import prepare_persona_study

_NOW = datetime(2026, 2, 1, tzinfo=UTC)
_ADDED_PATHS = {
    INITIAL_LABELS_PATH,
    INITIAL_RECEIPT_PATH,
    SEALED_LABELS_PATH,
    SEAL_RECEIPT_PATH,
}


def _completed_study(tmp_path: Path) -> tuple[PersonaStudyStore, str]:
    source, _ = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    result = prepare_persona_study(source, private, synthetic=True, evaluation_time=_NOW)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=_NOW)
    template = json.loads(result.labels_path.read_text(encoding="utf-8"))
    cards = json.loads((result.review_path.parent / "presentations.json").read_text("utf-8"))
    focus = {item["presentation_id"]: item["focus"]["content"] for item in cards}
    template["completed_by"] = "represented_user"
    for label in template["labels"]:
        text = focus[label["presentation_id"]]
        label.update(
            {
                "authorship": "self",
                "claim_holder": "self",
                "adoption": "endorsed",
                "decision": "accept",
                "target_layer": "persona",
                "persona_kind": "preference",
                "scope": {
                    "project": None,
                    "role": None,
                    "audience": None,
                    "risk": "low",
                    "temporal": None,
                },
                "rationale_spans": [{"start": 0, "end": 1, "text": text[:1]}],
                "evidence_demand_spans": [],
                "should_abstain": False,
                "exclude_from_persona": False,
                "exclusion_reason": None,
                "confidence": "high",
                "notes": None,
            }
        )
    result.labels_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    return store, result.manifest.study_id


def _has_receipt(entries: tuple[object, ...]) -> bool:
    return any(getattr(item, "relative_path", None) == INITIAL_RECEIPT_PATH for item in entries)


def test_post_commit_verification_failure_restores_mutable_state_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id = _completed_study(tmp_path)
    previous = store.read_index(study_id)
    original_verify = PersonaStudyStore._verify_entries
    injected = False

    def fail_post_commit(
        self: PersonaStudyStore, target_study_id: str, entries: tuple[object, ...]
    ) -> None:
        nonlocal injected
        if _has_receipt(entries) and not injected:
            injected = True
            raise DataValidationError("injected_post_commit", "Synthetic post-commit failure.")
        original_verify(self, target_study_id, entries)

    monkeypatch.setattr(PersonaStudyStore, "_verify_entries", fail_post_commit)
    with pytest.raises(DataValidationError) as error:
        submit_persona_labels(store, study_id)

    assert error.value.code == "injected_post_commit"
    restored = store.read_index(study_id)
    assert restored == previous
    assert (
        next(item for item in restored.entries if item.relative_path == LABEL_PATH).mutable_by
        != "none"
    )
    assert not (_ADDED_PATHS & {item.relative_path for item in restored.entries})
    assert all(not store.paths.artifact(study_id, path).exists() for path in _ADDED_PATHS)

    monkeypatch.setattr(PersonaStudyStore, "_verify_entries", original_verify)
    retried = submit_persona_labels(store, study_id)
    assert retried.seal_receipt is not None
    assert _ADDED_PATHS <= {item.relative_path for item in retried.artifact_index.entries}


def test_rollback_write_failure_preserves_committed_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id = _completed_study(tmp_path)
    original_verify = PersonaStudyStore._verify_entries
    original_write = PersonaStudyStore._write_index
    committed = False

    def fail_post_commit(
        self: PersonaStudyStore, target_study_id: str, entries: tuple[object, ...]
    ) -> None:
        if _has_receipt(entries):
            raise OSError("synthetic post-commit verification failure")
        original_verify(self, target_study_id, entries)

    def fail_rollback(self: PersonaStudyStore, index: StudyArtifactIndex) -> None:
        nonlocal committed
        entries = index.entries
        if committed and not _has_receipt(entries):
            raise OSError("synthetic rollback write failure")
        original_write(self, index)
        committed = _has_receipt(entries)

    monkeypatch.setattr(PersonaStudyStore, "_verify_entries", fail_post_commit)
    monkeypatch.setattr(PersonaStudyStore, "_write_index", fail_rollback)
    with pytest.raises(DataValidationError) as error:
        submit_persona_labels(store, study_id)

    assert error.value.code == "persona_study_rollback_incomplete"
    monkeypatch.setattr(PersonaStudyStore, "_verify_entries", original_verify)
    monkeypatch.setattr(PersonaStudyStore, "_write_index", original_write)
    index = store.read_index(study_id)
    paths = {item.relative_path for item in index.entries}
    assert _ADDED_PATHS <= paths
    assert (
        next(item for item in index.entries if item.relative_path == LABEL_PATH).mutable_by
        == "none"
    )
    assert all(store.paths.artifact(study_id, path).is_file() for path in _ADDED_PATHS)
