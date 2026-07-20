from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from test_persona_reaction_benchmark import _dataset, _split
from test_persona_reaction_scoring import _MODEL_BINDINGS, _predictions, _target_set

from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.full_persona import reaction_freeze, reaction_model, reaction_scoring
from ynoy.full_persona import reaction_verified as verified_module
from ynoy.full_persona.reaction_freeze import freeze_reaction_predictions
from ynoy.full_persona.reaction_model import LocalReactionModelAdapter
from ynoy.full_persona.reaction_scoring import score_reaction_predictions
from ynoy.full_persona.reaction_verified import run_verified_reaction_benchmark
from ynoy.models.persona_reaction_results import (
    PersonaReactionPredictionFreeze,
    PersonaReactionTargetSet,
)
from ynoy.util import canonical_sha256, sha256_file


def _adapter(path: Path) -> LocalReactionModelAdapter:
    return LocalReactionModelAdapter(
        endpoint="http://127.0.0.1:18100/v1/chat/completions",
        model="ynoy-test-local-8b",
        revision="synthetic-revision-1",
        artifact_sha256=sha256_file(path),
        artifact_path=path,
        local_attested=True,
    )


def _synthetic_freeze(split):
    return freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )


def _private_freeze(split) -> PersonaReactionPredictionFreeze:
    source = _synthetic_freeze(split)
    payload = source.model_dump(mode="json", exclude={"freeze_sha256"})
    payload.update(synthetic=False, upstream_run_sha256s=["b" * 64, "c" * 64])
    return PersonaReactionPredictionFreeze.model_validate(
        {**payload, "freeze_sha256": canonical_sha256(payload)}
    )


def _private_targets(split, freeze: PersonaReactionPredictionFreeze) -> PersonaReactionTargetSet:
    source = _target_set(split, _synthetic_freeze(split))
    payload = source.model_dump(mode="json", exclude={"target_set_sha256"})
    payload.update(
        synthetic=False,
        prediction_freeze_sha256=freeze.freeze_sha256,
        source_manifest_sha256="d" * 64,
        source_head_sha256="e" * 64,
        source_head_revision=1,
    )
    return PersonaReactionTargetSet.model_validate(
        {**payload, "target_set_sha256": canonical_sha256(payload)}
    )


def _forged_targets(targets: PersonaReactionTargetSet) -> PersonaReactionTargetSet:
    changed = list(targets.targets)
    item = changed[0]
    item_payload = item.model_dump(mode="json", exclude={"target_sha256"})
    item_payload["label"] = "decision" if item.label != "decision" else "correction"
    changed[0] = type(item).model_validate(
        {**item_payload, "target_sha256": canonical_sha256(item_payload)}
    )
    payload = targets.model_dump(mode="json", exclude={"target_set_sha256"})
    payload["targets"] = [item.model_dump(mode="json") for item in changed]
    return PersonaReactionTargetSet.model_validate(
        {**payload, "target_set_sha256": canonical_sha256(payload)}
    )


def _abstaining_transport(calls: list[dict[str, object]]):
    def fake_post(_endpoint: str, payload: dict[str, object], **_: object):
        calls.append(payload)
        candidate = {
            "predicted_label": "abstain",
            "ranking_score": 0.0,
            "evidence_ids": [],
        }
        return {
            "model": payload["model"],
            "choices": [{"message": {"content": json.dumps(candidate)}}],
        }

    return fake_post


def test_public_exports_have_one_verified_benchmark_entrypoint() -> None:
    forbidden = {
        "run_verified_reaction_model_arms",
        "freeze_verified_reaction_predictions",
        "score_verified_reaction_predictions",
    }
    modules = (reaction_model, reaction_freeze, reaction_scoring, verified_module)
    assert all(not (set(getattr(module, "__all__", ())) & forbidden) for module in modules)
    assert set(verified_module.__all__) == {
        "VerifiedReactionBenchmark",
        "run_verified_reaction_benchmark",
    }
    assert all(not hasattr(verified_module, name) for name in forbidden)
    assert tuple(inspect.signature(run_verified_reaction_benchmark).parameters) == (
        "adapter",
        "store",
        "source_manifest",
        "source_head",
    )


def test_direct_private_entrypoints_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    split = _split()
    private_manifest = split.manifest.model_copy(update={"synthetic": False})
    adapter = LocalReactionModelAdapter(
        endpoint="http://127.0.0.1:18100/v1/chat/completions",
        model="ynoy-test-local-8b",
        revision="synthetic-revision-1",
        artifact_sha256="a" * 64,
        local_attested=True,
    )
    monkeypatch.setattr(
        "ynoy.full_persona.reaction_model.post_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("transport called")),
    )
    with pytest.raises(DataValidationError):
        adapter.predict_arm(private_manifest, split.history, split.cases, arm="structured_persona")
    with pytest.raises(DataValidationError):
        freeze_reaction_predictions(
            private_manifest,
            split.target_seal,
            cases=split.cases,
            predictions=_predictions(split),
            model_bindings=_MODEL_BINDINGS,
        )
    private_freeze = _private_freeze(split)
    with pytest.raises(PolicyViolation):
        score_reaction_predictions(
            private_freeze,
            _private_targets(split, private_freeze),
        )


def test_verified_benchmark_rechecks_artifact_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "model.bin"
    path.write_bytes(b"pinned-model")
    adapter = _adapter(path)
    path.write_bytes(b"changed-after-construction")
    monkeypatch.setattr(
        verified_module,
        "build_verified_reaction_split",
        lambda *_args: _split(),
    )
    monkeypatch.setattr(
        verified_module,
        "post_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("transport called")),
    )
    with pytest.raises(DataValidationError):
        run_verified_reaction_benchmark(adapter, object(), object(), object())


def test_verified_benchmark_rejects_invalid_source_chain(tmp_path: Path) -> None:
    path = tmp_path / "model.bin"
    path.write_bytes(b"pinned-model")
    source_manifest, _evidence = _dataset()
    with pytest.raises(DataValidationError):
        run_verified_reaction_benchmark(_adapter(path), object(), source_manifest, object())


def test_verified_benchmark_rematerializes_targets_without_caller_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "model.bin"
    path.write_bytes(b"pinned-model")
    split = _split()
    calls: list[dict[str, object]] = []
    materialized: list[PersonaReactionTargetSet] = []

    def materialize(_store, _manifest, _head, _reaction, _seal, freeze):
        target_set = _private_targets(split, freeze)
        materialized.append(target_set)
        return target_set

    monkeypatch.setattr(verified_module, "build_verified_reaction_split", lambda *_: split)
    monkeypatch.setattr(verified_module, "post_json", _abstaining_transport(calls))
    monkeypatch.setattr(verified_module, "materialize_reaction_targets", materialize)
    result = run_verified_reaction_benchmark(_adapter(path), object(), object(), object())
    forged = _forged_targets(result.target_set)
    assert len(calls) == 48
    assert materialized == [result.target_set]
    assert result.target_set != forged
    assert result.result.target_set_sha256 == result.target_set.target_set_sha256
