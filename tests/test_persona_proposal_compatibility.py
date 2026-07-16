from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.persona_assisted import FakeProposer, prepared_study

from ynoy.cli.main import main
from ynoy.models import DataClass, PersonaProposalBundle
from ynoy.persona_study import assisted_labels as assisted_module
from ynoy.persona_study.assisted_attempts import build_attempt_payloads
from ynoy.persona_study.assisted_labels import propose_assisted_labels
from ynoy.util import canonical_sha256


def test_legacy_01_bundle_without_guard_method_or_count_remains_replayable(
    tmp_path: Path,
) -> None:
    store, prepared = prepared_study(tmp_path)
    current = propose_assisted_labels(
        store, prepared.manifest.study_id, FakeProposer()
    ).bundle.model_dump(mode="json")
    receipt = current["receipt"]
    receipt["schema_version"] = "persona-model-proposals/0.1"
    receipt.pop("deterministic_guard_pass_count")
    for proposal in current["proposals"]:
        for pass_name in ("direct", "skeptical"):
            if proposal[pass_name] is not None:
                proposal[pass_name].pop("method")
    receipt["proposal_set_sha256"] = canonical_sha256(current["proposals"])
    receipt["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )

    replayed = PersonaProposalBundle.model_validate(current)

    assert replayed.receipt.schema_version == "persona-model-proposals/0.1"
    assert replayed.receipt.deterministic_guard_pass_count == 0


def test_real_shaped_proposal_and_review_payloads_retain_raw_corpus_class(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    result = propose_assisted_labels(store, prepared.manifest.study_id, FakeProposer())
    real_index = result.artifact_index.model_copy(
        update={
            "entries": tuple(
                entry.model_copy(update={"data_class": DataClass.RAW_CORPUS})
                for entry in result.artifact_index.entries
            )
        }
    )

    payloads = build_attempt_payloads(
        real_index,
        result.bundle,
        assisted_module.presentations(store, prepared.manifest.study_id),
        "evaluator/model-proposals.classification-check.json",
        "primary",
        None,
    )

    assert payloads
    assert all(payload.data_class == DataClass.RAW_CORPUS for payload in payloads)


def test_cli_requires_explicit_model_identity_before_proposer_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store, prepared = prepared_study(tmp_path, evaluation_time=datetime.now(UTC))
    monkeypatch.setenv("YNOY_LOCAL_REASONER_URL", "http://127.0.0.1:18100/v1/chat/completions")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_REVISION", "fixture-r1")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_ARTIFACT_SHA256", "d" * 64)
    monkeypatch.setenv("YNOY_LOCAL_MODEL_ATTESTED", "true")
    monkeypatch.delenv("YNOY_LOCAL_REASONER_MODEL", raising=False)
    monkeypatch.setattr(
        "ynoy.cli.handlers.study_proposals.LocalPersonaProposer",
        lambda **_kwargs: pytest.fail("proposer must not be constructed"),
    )

    exit_code = main(
        [
            "--indent",
            "0",
            "--private-root",
            str(store.root),
            "study",
            "propose-labels",
            prepared.manifest.study_id,
            "--synthetic",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["error"]["code"] == "persona_proposer_not_configured"
