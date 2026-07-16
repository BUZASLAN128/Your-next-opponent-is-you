from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.errors import DataValidationError
from ynoy.models import CompletedRepeatAdjudicationSet, PersonaInitialLabelReceipt
from ynoy.persona_study.artifact_contract import artifact_index
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.label_contract import (
    ADJUDICATION_PATH,
    INITIAL_LABELS_PATH,
    INITIAL_RECEIPT_PATH,
    LABEL_PATH,
    SEAL_RECEIPT_PATH,
    SEALED_LABELS_PATH,
)
from ynoy.persona_study.label_submission import submit_persona_labels
from ynoy.persona_study.labels import seal_persona_labels
from ynoy.persona_study.prepare import prepare_persona_study
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _completed_study(tmp_path: Path, *, mismatch: bool) -> tuple[PersonaStudyStore, str, Path]:
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
    if mismatch:
        mapping = json.loads(
            store.read_artifact(result.manifest.study_id, "evaluator/blind-map.json")
        )
        repeated = next(item for item in mapping if item["repeated"])
        labels = {item["presentation_id"]: item for item in template["labels"]}
        labels[repeated["presentation_id"]]["decision"] = "reject"
    result.labels_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    return store, result.manifest.study_id, result.labels_path


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


def _complete_adjudication(store: PersonaStudyStore, study_id: str) -> Path:
    path = store.paths.artifact(study_id, ADJUDICATION_PATH)
    value = json.loads(store.read_artifact(study_id, ADJUDICATION_PATH, allow_user_draft=True))
    value["completed_by"] = "represented_user"
    for item in value["adjudications"]:
        item["final_judgment"] = item["initial_judgments"][0]
        item["adjudication_reason"] = "Synthetic represented-user resolution."
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _change_before_locked_seal(
    monkeypatch: pytest.MonkeyPatch,
    draft_path: Path,
    action: Callable[[], object],
) -> DataValidationError:
    original = PersonaStudyStore.seal_mutable_artifact
    barrier = Barrier(2)

    def pause_before_lock(
        self: PersonaStudyStore,
        study_id: str,
        mutable_path: str,
        payloads: tuple[object, ...],
        *,
        expected_mutable_sha256: str,
    ) -> object:
        barrier.wait(timeout=10)
        barrier.wait(timeout=10)
        return original(
            self,
            study_id,
            mutable_path,
            payloads,
            expected_mutable_sha256=expected_mutable_sha256,
        )

    monkeypatch.setattr(PersonaStudyStore, "seal_mutable_artifact", pause_before_lock)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(action)
        barrier.wait(timeout=10)
        draft_path.write_bytes(draft_path.read_bytes() + b"\n")
        barrier.wait(timeout=10)
        with pytest.raises(DataValidationError) as error:
            future.result(timeout=20)
    return error.value


def _replace_indexed_artifact(
    store: PersonaStudyStore, study_id: str, relative_path: str, content: bytes
) -> None:
    index = store.read_index(study_id)
    entries = tuple(
        item.model_copy(update={"sha256": sha256_bytes(content)})
        if item.relative_path == relative_path
        else item
        for item in index.entries
    )
    updated = artifact_index(study_id, index.created_at, index.expires_at, entries)
    store.paths.artifact(study_id, relative_path).write_bytes(content)
    store.paths.index(study_id).write_bytes(canonical_json_bytes(updated.model_dump(mode="json")))


def test_label_draft_change_after_compute_fails_without_initial_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id, draft = _completed_study(tmp_path, mismatch=False)

    error = _change_before_locked_seal(
        monkeypatch, draft, lambda: submit_persona_labels(store, study_id)
    )

    assert error.code == "persona_study_mutable_changed"
    index = store.read_index(study_id)
    paths = {item.relative_path for item in index.entries}
    assert INITIAL_LABELS_PATH not in paths and INITIAL_RECEIPT_PATH not in paths
    assert (
        next(item for item in index.entries if item.relative_path == LABEL_PATH).mutable_by
        != "none"
    )


def test_adjudication_change_after_compute_fails_without_final_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, study_id, _ = _completed_study(tmp_path, mismatch=True)
    submit_persona_labels(store, study_id)
    draft = _complete_adjudication(store, study_id)

    error = _change_before_locked_seal(
        monkeypatch, draft, lambda: seal_persona_labels(store, study_id)
    )

    assert error.code == "persona_study_mutable_changed"
    index = store.read_index(study_id)
    paths = {item.relative_path for item in index.entries}
    assert SEALED_LABELS_PATH not in paths and SEAL_RECEIPT_PATH not in paths
    assert (
        next(item for item in index.entries if item.relative_path == ADJUDICATION_PATH).mutable_by
        != "none"
    )


def test_final_replay_rejects_reindexed_initial_receipt_rewrite(tmp_path: Path) -> None:
    store, study_id, _ = _completed_study(tmp_path, mismatch=False)
    submit_persona_labels(store, study_id)
    value = json.loads(store.read_artifact(study_id, INITIAL_RECEIPT_PATH))
    value["field_agreement_counts"]["decision"] -= 1
    value["receipt_sha256"] = canonical_sha256(
        {key: item for key, item in value.items() if key != "receipt_sha256"}
    )
    receipt = PersonaInitialLabelReceipt.model_validate(value)
    _replace_indexed_artifact(
        store,
        study_id,
        INITIAL_RECEIPT_PATH,
        canonical_json_bytes(receipt.model_dump(mode="json")),
    )

    with pytest.raises(DataValidationError) as error:
        seal_persona_labels(store, study_id)

    assert error.value.code == "persona_label_seal_ancestor_mismatch"


def test_final_replay_rejects_reindexed_adjudication_rewrite(tmp_path: Path) -> None:
    store, study_id, _ = _completed_study(tmp_path, mismatch=True)
    submit_persona_labels(store, study_id)
    _complete_adjudication(store, study_id)
    seal_persona_labels(store, study_id)
    value = json.loads(store.read_artifact(study_id, ADJUDICATION_PATH))
    value["adjudications"][0]["adjudication_reason"] = "Rewritten synthetic resolution."
    adjudication = CompletedRepeatAdjudicationSet.model_validate(value)
    _replace_indexed_artifact(
        store,
        study_id,
        ADJUDICATION_PATH,
        canonical_json_bytes(adjudication.model_dump(mode="json")),
    )

    with pytest.raises(DataValidationError) as error:
        seal_persona_labels(store, study_id)

    assert error.value.code == "persona_label_seal_ancestor_mismatch"
