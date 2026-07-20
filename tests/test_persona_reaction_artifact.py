from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_persona_reaction_benchmark import _dataset, _split
from test_persona_reaction_scoring import _predictions, _target_set

from ynoy.errors import DataValidationError
from ynoy.full_persona.deletion import delete_full_persona_run
from ynoy.full_persona.reaction_artifact import build_reaction_artifact
from ynoy.full_persona.reaction_artifact_store import FullPersonaReactionStore
from ynoy.full_persona.reaction_baselines import run_reaction_baselines
from ynoy.full_persona.reaction_contracts import seal_model
from ynoy.full_persona.store import FullPersonaStore
from ynoy.full_persona.store_contract import seal_full_corpus_head
from ynoy.models.base import DataClass
from ynoy.models.full_persona import FullCorpusManifest
from ynoy.models.persona_reaction_artifact import PersonaReactionBenchmarkArtifact
from ynoy.models.persona_reaction_results import (
    PersonaReactionComparisonResult,
    PersonaReactionModelRun,
    PersonaReactionPredictionFreeze,
    PersonaReactionTargetSet,
)
from ynoy.util import canonical_sha256


def _real_source_run(tmp_path: Path) -> tuple[Path, FullCorpusManifest, object]:
    source, _evidence = _dataset()
    files = (source.files[0],)
    payload = source.model_dump(mode="json", exclude={"run_id", "manifest_sha256"})
    payload.update(
        run_id=canonical_sha256({"real-fixture": source.run_id}),
        source_data_class=DataClass.RAW_CORPUS,
        synthetic=False,
        files=[files[0].model_dump(mode="json")],
        expected_file_count=1,
        expected_input_bytes=files[0].file_bytes,
        source_snapshot_sha256=canonical_sha256([files[0].model_dump(mode="json")]),
    )
    manifest = FullCorpusManifest.model_validate(
        {**payload, "manifest_sha256": canonical_sha256(payload)}
    )
    root = tmp_path / "private"
    store = FullPersonaStore(root, synthetic=False)
    initial = store.write_manifest(manifest)
    complete_payload = initial.model_dump(mode="python", exclude={"head_sha256"})
    complete_payload.update(
        revision=1,
        status="complete",
        previous_head_sha256=initial.head_sha256,
    )
    store.commit_revision(initial, seal_full_corpus_head(complete_payload))
    return root, manifest, store.read_head(manifest.run_id)


def _private_benchmark(manifest: FullCorpusManifest, head: object):
    split = _split()
    baseline = run_reaction_baselines(
        split.manifest,
        split.history,
        split.cases,
        expected_manifest_sha256=split.manifest.manifest_sha256,
    )
    model = _private_model(split)
    synthetic_freeze = PersonaReactionPredictionFreeze.model_validate(
        {
            **_target_freeze_payload(split),
            "freeze_sha256": canonical_sha256(_target_freeze_payload(split)),
        }
    )
    freeze_payload = synthetic_freeze.model_dump(mode="json", exclude={"freeze_sha256"})
    freeze_payload.update(
        synthetic=False,
        upstream_run_sha256s=(baseline.run_sha256, model.run_sha256),
    )
    freeze = PersonaReactionPredictionFreeze.model_validate(
        {**freeze_payload, "freeze_sha256": canonical_sha256(freeze_payload)}
    )
    target_source = _target_set(split, synthetic_freeze)
    target_payload = target_source.model_dump(mode="json", exclude={"target_set_sha256"})
    target_payload.update(
        synthetic=False,
        prediction_freeze_sha256=freeze.freeze_sha256,
        source_manifest_sha256=manifest.manifest_sha256,
        source_head_sha256=head.head_sha256,
        source_head_revision=head.revision,
    )
    targets = PersonaReactionTargetSet.model_validate(
        {**target_payload, "target_set_sha256": canonical_sha256(target_payload)}
    )
    result_source = _score_result(synthetic_freeze, target_source)
    result_payload = result_source.model_dump(mode="json", exclude={"result_sha256"})
    result_payload.update(
        prediction_freeze_sha256=freeze.freeze_sha256,
        target_set_sha256=targets.target_set_sha256,
    )
    result = PersonaReactionComparisonResult.model_validate(
        {**result_payload, "result_sha256": canonical_sha256(result_payload)}
    )
    from ynoy.full_persona.reaction_verified import VerifiedReactionBenchmark

    return VerifiedReactionBenchmark(baseline, model, freeze, targets, result)


def _private_model(split) -> PersonaReactionModelRun:
    predictions = _predictions(split)
    payload = {
        "manifest_sha256": split.manifest.manifest_sha256,
        "model": "synthetic-local-8b",
        "revision": "fixture-revision",
        "artifact_sha256": "a" * 64,
        "decode_sha256": "b" * 64,
        "predictions": {
            arm: [item.model_dump(mode="json") for item in predictions[arm]]
            for arm in ("generic_local_8b", "structured_persona")
        },
        "source_synthetic": False,
        "local_attested": True,
        "artifact_file_verified": True,
        "endpoint_authentication": "not_cryptographically_authenticated",
        "targets_revealed": False,
        "calibration_used": False,
        "persona_identity_claimed": False,
    }
    return seal_model(PersonaReactionModelRun, payload, "run_sha256")


def _target_freeze_payload(split):
    from ynoy.full_persona.reaction_freeze import freeze_reaction_predictions

    value = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings={arm: "fixture" for arm in split.manifest.arms},
    )
    return value.model_dump(mode="json", exclude={"freeze_sha256"})


def _score_result(freeze: PersonaReactionPredictionFreeze, targets: PersonaReactionTargetSet):
    from ynoy.full_persona.reaction_scoring import score_reaction_predictions

    return score_reaction_predictions(freeze, targets)


def test_artifact_build_is_deterministic_and_chain_bound(tmp_path: Path) -> None:
    _root, manifest, head = _real_source_run(tmp_path)
    benchmark = _private_benchmark(manifest, head)
    first = build_reaction_artifact(manifest, head, benchmark)
    second = build_reaction_artifact(manifest, head, benchmark)

    assert first == second
    assert first.artifact_id == canonical_sha256(
        {
            "source_run_id": manifest.run_id,
            "source_head_sha256": head.head_sha256,
            "prediction_freeze_sha256": first.prediction_freeze.freeze_sha256,
            "target_set_sha256": first.target_set.target_set_sha256,
            "result_sha256": first.result.result_sha256,
        }
    )
    assert first.artifact_sha256 == canonical_sha256(
        first.model_dump(mode="json", exclude={"artifact_sha256"})
    )
    assert first.target_set.source_manifest_sha256 == manifest.manifest_sha256
    assert first.target_set.source_head_sha256 == head.head_sha256


def test_artifact_chain_tamper_is_rejected(tmp_path: Path) -> None:
    _root, manifest, head = _real_source_run(tmp_path)
    artifact = build_reaction_artifact(manifest, head, _private_benchmark(manifest, head))
    tampered = artifact.model_dump(mode="json")
    tampered["result"]["reason"] = "tampered"
    with pytest.raises(ValueError, match=r"result_sha256|artifact hash"):
        PersonaReactionBenchmarkArtifact.model_validate(tampered)

    stale = artifact.model_dump(mode="json")
    stale["source_head_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="identifier"):
        PersonaReactionBenchmarkArtifact.model_validate(stale)


def test_private_store_roundtrip_and_pointer_tamper_fail_closed(tmp_path: Path) -> None:
    root, manifest, head = _real_source_run(tmp_path)
    artifact = build_reaction_artifact(manifest, head, _private_benchmark(manifest, head))
    store = FullPersonaReactionStore(root)
    path = store.write(artifact)

    assert path.is_file()
    assert store.read(manifest.run_id) == artifact

    pointer = path.parent / "latest.json"
    pointer.write_text(
        json.dumps({"artifact_id": artifact.artifact_id, "artifact_sha256": "0" * 64}),
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError) as error:
        store.read(manifest.run_id)
    assert error.value.details["reason"] == "reaction artifact pointer is stale"

    pointer.write_bytes(
        json.dumps(
            {"artifact_id": artifact.artifact_id, "artifact_sha256": artifact.artifact_sha256}
        ).encode()
    )
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataValidationError, match="invalid"):
        store.read(manifest.run_id)


def test_full_persona_deletion_removes_nested_reaction_artifact(tmp_path: Path) -> None:
    root, manifest, head = _real_source_run(tmp_path)
    artifact = build_reaction_artifact(manifest, head, _private_benchmark(manifest, head))
    artifact_path = FullPersonaReactionStore(root).write(artifact)
    assert artifact_path.is_file()

    deleted = delete_full_persona_run(root, manifest.run_id, synthetic=False)

    assert deleted > 0
    assert not artifact_path.exists()
    assert not (root / "full-persona-packs" / manifest.run_id).exists()
    with pytest.raises(DataValidationError):
        FullPersonaReactionStore(root).read(manifest.run_id)
