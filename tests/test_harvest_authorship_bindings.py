from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.harvest_authorship import (
    authorship_submission,
    prepare_authorship_fixture,
    replace_indexed_artifact,
)

from ynoy.errors import DataValidationError
from ynoy.models.persona_harvest import HarvestCheckpoint
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.harvest_authorship import submit_harvest_authorship
from ynoy.persona_study.harvest_contract import seal_harvest_cursor
from ynoy.util import canonical_sha256


def _checkpoint_path(store: PersonaStudyStore, run_id: str, revision: int) -> Path:
    return store.paths.artifact(run_id, f"evaluator/harvest-checkpoint-{revision:04d}.json")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "f" * 64),
        ("source_study_id", "e" * 64),
        ("holdout_freeze_sha256", "d" * 64),
        ("selector_config_sha256", "c" * 64),
    ],
)
def test_valid_foreign_cursor_binding_hash_is_rejected(
    tmp_path: Path, field: str, value: str
) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    relative = f"evaluator/harvest-checkpoint-{prepared.checkpoint.cursor.revision:04d}.json"
    path = _checkpoint_path(store, prepared.manifest.run_id, prepared.checkpoint.cursor.revision)
    checkpoint = HarvestCheckpoint.model_validate_json(path.read_bytes())
    values = checkpoint.cursor.model_dump(mode="python")
    values[field] = value
    cursor = seal_harvest_cursor(
        run_id=values["run_id"],
        source_study_id=values["source_study_id"],
        freeze_sha256=values["holdout_freeze_sha256"],
        stable_before_ns=values["stable_before_ns"],
        selector_config_sha256=values["selector_config_sha256"],
        revision=values["revision"],
        last_file=checkpoint.cursor.last_file,
        complete=values["status"] == "complete",
    )
    payload = {
        **checkpoint.model_dump(mode="json", exclude={"checkpoint_sha256"}),
        "cursor": cursor.model_dump(mode="json"),
    }
    forged = HarvestCheckpoint.model_validate(
        {**payload, "checkpoint_sha256": canonical_sha256(payload)}
    )
    replace_indexed_artifact(
        store,
        prepared.manifest.run_id,
        relative,
        json.dumps(forged.model_dump(mode="json"), separators=(",", ":")).encode(),
    )

    with pytest.raises(DataValidationError):
        submit_harvest_authorship(store, authorship_submission(prepared))


def test_index_consistent_forged_review_is_rejected(tmp_path: Path) -> None:
    _, private, prepared, now = prepare_authorship_fixture(tmp_path)
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)
    relative = f"annotator/harvest-review-{prepared.checkpoint.cursor.revision:04d}.md"
    replace_indexed_artifact(
        store,
        prepared.manifest.run_id,
        relative,
        b"# forged review\nThis is not derived from the checkpoint.\n",
    )

    with pytest.raises(DataValidationError):
        submit_harvest_authorship(store, authorship_submission(prepared))
