from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.errors import DataValidationError
from ynoy.models import (
    CompletedPersonaLabelSet,
    DataClass,
    PersonaInitialLabelReceipt,
)
from ynoy.persona_study import artifacts as artifact_module
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.label_contract import INITIAL_LABELS_PATH, INITIAL_RECEIPT_PATH, LABEL_PATH
from ynoy.persona_study.label_submission import PersonaLabelSubmission, submit_persona_labels
from ynoy.persona_study.prepare import PreparedPersonaStudy, prepare_persona_study
from ynoy.persona_study.transactions import exclusive_write_bytes
from ynoy.util import canonical_sha256

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _completed_study(tmp_path: Path) -> tuple[PersonaStudyStore, PreparedPersonaStudy]:
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
        label.update(_judgment(text))
    result.labels_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    return store, result


def _judgment(text: str) -> dict[str, object]:
    return {
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


def _simple_run(
    root: Path, *, now: datetime, expires_at: datetime
) -> tuple[PersonaStudyStore, str]:
    store = PersonaStudyStore(root, real_data=False, evaluation_time=now)
    study_id = canonical_sha256((str(root), "study"))
    store.write_run(
        study_id,
        (
            ArtifactPayload(
                "evaluator/indexed.json",
                b"{}",
                DataClass.PUBLIC_SYNTHETIC,
                (canonical_sha256((study_id, "source")),),
            ),
        ),
        created_at=now,
        expires_at=expires_at,
    )
    return store, study_id


def test_partial_seal_failure_rolls_back_added_files_and_keeps_draft_mutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, result = _completed_study(tmp_path)
    study_id = result.manifest.study_id
    original_draft = store.read_artifact(study_id, LABEL_PATH, allow_user_draft=True)
    original_write = artifact_module.exclusive_write_bytes
    calls = 0

    def fail_after_first(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected synthetic write failure")
        original_write(path, content)

    monkeypatch.setattr(artifact_module, "exclusive_write_bytes", fail_after_first)
    with pytest.raises(OSError, match="injected synthetic"):
        submit_persona_labels(store, study_id)

    index = store.read_index(study_id)
    draft = next(item for item in index.entries if item.relative_path == LABEL_PATH)
    assert draft.mutable_by == "represented_user"
    assert store.read_artifact(study_id, LABEL_PATH, allow_user_draft=True) == original_draft
    assert all(
        item.relative_path not in {INITIAL_LABELS_PATH, INITIAL_RECEIPT_PATH}
        for item in index.entries
    )
    assert not store.paths.artifact(study_id, INITIAL_LABELS_PATH).exists()
    assert not store.paths.lock(study_id).exists()


def test_source_closure_index_failure_keeps_index_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "private"
    store = PersonaStudyStore(private, real_data=False, evaluation_time=_NOW)
    study_id = canonical_sha256("source-closure-rollback")
    dependency = canonical_sha256("source-closure-dependency")
    store.write_run(
        study_id,
        (
            ArtifactPayload("evaluator/keep.json", b"keep", DataClass.PUBLIC_SYNTHETIC, ("other",)),
            ArtifactPayload(
                "evaluator/remove.json",
                b"remove",
                DataClass.PUBLIC_SYNTHETIC,
                (dependency,),
            ),
        ),
        created_at=_NOW,
        expires_at=_NOW + timedelta(days=7),
    )
    index_path = store.paths.index(study_id)
    before_index = index_path.read_bytes()
    before_files = {
        path: store.paths.artifact(study_id, path).read_bytes()
        for path in ("evaluator/keep.json", "evaluator/remove.json")
    }

    def fail_index(_index: object) -> None:
        raise OSError("injected index failure")

    monkeypatch.setattr(store, "_write_index", fail_index)
    with pytest.raises(OSError, match="injected index"):
        store.delete_source_closure(study_id, dependency)

    assert index_path.read_bytes() == before_index
    assert {
        path: store.paths.artifact(study_id, path).read_bytes() for path in before_files
    } == before_files
    assert store.read_index(study_id).study_id == study_id


def test_run_delete_index_failure_keeps_index_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id = _simple_run(
        tmp_path / "private", now=_NOW, expires_at=_NOW + timedelta(days=7)
    )
    index_path = store.paths.index(study_id)
    artifact_path = store.paths.artifact(study_id, "evaluator/indexed.json")
    before_index = index_path.read_bytes()
    before_artifact = artifact_path.read_bytes()
    original_unlink = Path.unlink

    def fail_index_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == index_path:
            raise OSError("injected index unlink failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_index_unlink)
    with pytest.raises(OSError, match="injected index unlink"):
        store.delete_run(study_id)

    assert index_path.read_bytes() == before_index
    assert artifact_path.read_bytes() == before_artifact
    assert store.read_index(study_id).study_id == study_id


def test_concurrent_submissions_create_one_immutable_initial_evidence(tmp_path: Path) -> None:
    store, result = _completed_study(tmp_path)
    study_id = result.manifest.study_id
    barrier = Barrier(3)

    def submit() -> PersonaLabelSubmission | DataValidationError:
        barrier.wait()
        try:
            return submit_persona_labels(store, study_id)
        except DataValidationError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (pool.submit(submit), pool.submit(submit))
        barrier.wait()
        outcomes = tuple(item.result(timeout=20) for item in futures)

    successes = tuple(item for item in outcomes if isinstance(item, PersonaLabelSubmission))
    failures = tuple(item for item in outcomes if isinstance(item, DataValidationError))
    assert len(successes) == len(failures) == 1
    initial = CompletedPersonaLabelSet.model_validate_json(
        store.read_artifact(study_id, INITIAL_LABELS_PATH)
    )
    receipt = PersonaInitialLabelReceipt.model_validate_json(
        store.read_artifact(study_id, INITIAL_RECEIPT_PATH)
    )
    index = store.read_index(study_id)
    paths = tuple(item.relative_path for item in index.entries)
    assert paths.count(INITIAL_LABELS_PATH) == paths.count(INITIAL_RECEIPT_PATH) == 1
    assert receipt == successes[0].initial_receipt
    assert receipt.label_set_sha256 == canonical_sha256(initial.model_dump(mode="json"))


def test_preexisting_unindexed_target_is_not_overwritten_and_blocks_purge(tmp_path: Path) -> None:
    store, result = _completed_study(tmp_path)
    study_id = result.manifest.study_id
    target = store.paths.artifact(study_id, INITIAL_LABELS_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"preexisting-sentinel")

    with pytest.raises(DataValidationError) as exclusive:
        exclusive_write_bytes(target, b"replacement")
    purge = store.purge_expired(_NOW)
    with pytest.raises(DataValidationError) as access:
        store.read_index(study_id)

    assert exclusive.value.code == "persona_study_artifact_exists"
    assert purge.failed_run_count == 1
    assert access.value.code == "persona_study_expiry_purge_incomplete"
    assert target.read_bytes() == b"preexisting-sentinel"


def test_delete_fails_when_scoped_run_contains_unindexed_file(tmp_path: Path) -> None:
    store, study_id = _simple_run(
        tmp_path / "private", now=_NOW, expires_at=_NOW + timedelta(days=7)
    )
    extra = store.paths.evaluator_root / study_id / "extra.json"
    extra.write_bytes(b"unindexed")

    with pytest.raises(DataValidationError) as error:
        store.delete_run(study_id)

    assert error.value.code == "persona_study_expiry_purge_incomplete"
    assert extra.is_file() and store.paths.index(study_id).is_file()


def test_ttl_purge_fails_when_expired_run_contains_unindexed_file(tmp_path: Path) -> None:
    setup_time = _NOW - timedelta(days=8)
    private = tmp_path / "private"
    setup, study_id = _simple_run(private, now=setup_time, expires_at=_NOW - timedelta(days=1))
    extra = setup.paths.annotator_root / study_id / "extra.json"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"unindexed")
    store = PersonaStudyStore(private, real_data=False, evaluation_time=_NOW)

    result = store.purge_expired(_NOW)

    assert result.deleted_artifact_count == 0 and result.failed_run_count == 1
    assert extra.is_file() and store.paths.index(study_id).is_file()
