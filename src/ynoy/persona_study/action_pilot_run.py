from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from ynoy.errors import DataValidationError
from ynoy.models.base import DataClass
from ynoy.models.harvest_authorship import HarvestAuthorshipReceipt
from ynoy.models.persona_action_pilot import ActionPilotRun
from ynoy.models.persona_harvest import HarvestCheckpoint
from ynoy.models.persona_study import StudyArtifactIndex
from ynoy.persona_study.action_pilot import (
    freeze_action_predictions,
    prepare_action_pilot,
    score_action_pilot,
)
from ynoy.persona_study.action_predictor import LocalActionPredictor
from ynoy.persona_study.artifact_contract import ArtifactPayload
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.util import canonical_json_bytes

_AUTHORSHIP = re.compile(r"^evaluator/harvest-authorship-(\d{4})\.json$")
_PREFIX = "evaluator/observable-action-pilot-0.1"


@dataclass(frozen=True, slots=True)
class PrivateActionPilotResult:
    run: ActionPilotRun
    result_relative_path: str


def run_private_action_pilot(
    store: PersonaStudyStore,
    run_id: str,
    predictor: LocalActionPredictor,
) -> PrivateActionPilotResult:
    index = store.read_index(run_id)
    _require_fresh(index)
    receipt = _load_latest_authorship(store, run_id, index)
    checkpoint = _load_checkpoint(store, run_id, receipt.revision)
    manifest, history, cases, targets = prepare_action_pilot(checkpoint, receipt)
    dependencies = tuple(
        sorted(
            {
                receipt.receipt_sha256,
                *(item.source_receipt for item in history),
                *(item.source_receipt for item in cases),
            }
        )
    )
    generic = predictor.predict_arm(manifest, (), cases, arm="generic")
    personalized = predictor.predict_arm(manifest, history, cases, arm="personalized")
    freeze = freeze_action_predictions(manifest, generic, personalized)
    _write_inputs(store, run_id, manifest, history, cases, dependencies)
    store.append_artifacts(
        run_id,
        (
            _payload(
                "prediction-freeze.json",
                freeze,
                (*dependencies, manifest.manifest_sha256),
                DataClass.DERIVED_IDENTITY,
            ),
        ),
    )
    result = score_action_pilot(manifest, freeze, history, targets)
    _write_result(store, run_id, targets, result, dependencies, freeze.freeze_sha256)
    return PrivateActionPilotResult(result, f"{_PREFIX}/result.json")


def _write_inputs(
    store: PersonaStudyStore,
    run_id: str,
    manifest: BaseModel,
    history: tuple[BaseModel, ...],
    cases: tuple[BaseModel, ...],
    dependencies: tuple[str, ...],
) -> None:
    store.append_artifacts(
        run_id,
        (
            _payload("manifest.json", manifest, dependencies, DataClass.DERIVED_IDENTITY),
            _payload("history.json", history, dependencies, DataClass.RAW_CORPUS),
            _payload("cases.json", cases, dependencies, DataClass.RAW_CORPUS),
        ),
    )


def _write_result(
    store: PersonaStudyStore,
    run_id: str,
    targets: tuple[BaseModel, ...],
    result: BaseModel,
    dependencies: tuple[str, ...],
    freeze_sha256: str,
) -> None:
    bound = (*dependencies, freeze_sha256)
    store.append_artifacts(
        run_id,
        (
            _payload("targets.json", targets, bound, DataClass.DERIVED_IDENTITY),
            _payload("result.json", result, bound, DataClass.DERIVED_IDENTITY),
        ),
    )


def _require_fresh(index: StudyArtifactIndex) -> None:
    if any(item.relative_path.startswith(_PREFIX) for item in index.entries):
        raise DataValidationError(
            "action_pilot_already_started",
            "This immutable action pilot has already started; refusing to overwrite it.",
        )


def _load_latest_authorship(
    store: PersonaStudyStore, run_id: str, index: StudyArtifactIndex
) -> HarvestAuthorshipReceipt:
    matches = sorted(
        (item.relative_path for item in index.entries if _AUTHORSHIP.fullmatch(item.relative_path)),
        key=_authorship_revision,
    )
    if not matches:
        raise DataValidationError(
            "action_pilot_authorship_missing", "No sealed harvest authorship receipt exists."
        )
    try:
        content = store.read_artifact(run_id, matches[-1])
        return HarvestAuthorshipReceipt.model_validate_json(content)
    except ValidationError as exc:
        raise DataValidationError(
            "action_pilot_authorship_invalid", "The harvest authorship receipt is invalid."
        ) from exc


def _load_checkpoint(store: PersonaStudyStore, run_id: str, revision: int) -> HarvestCheckpoint:
    path = f"evaluator/harvest-checkpoint-{revision:04d}.json"
    try:
        return HarvestCheckpoint.model_validate_json(store.read_artifact(run_id, path))
    except ValidationError as exc:
        raise DataValidationError(
            "action_pilot_checkpoint_invalid", "The bound harvest checkpoint is invalid."
        ) from exc


def _payload(
    name: str,
    value: BaseModel | tuple[BaseModel, ...],
    dependencies: tuple[str, ...],
    data_class: DataClass,
) -> ArtifactPayload:
    body: object
    if isinstance(value, tuple):
        body = [item.model_dump(mode="json") for item in value]
    else:
        body = value.model_dump(mode="json")
    return ArtifactPayload(
        f"{_PREFIX}/{name}",
        canonical_json_bytes(body),
        data_class,
        tuple(sorted(set(dependencies))),
    )


def _authorship_revision(path: str) -> int:
    match = _AUTHORSHIP.fullmatch(path)
    if match is None:
        raise ValueError("not an authorship receipt path")
    return int(match.group(1))
