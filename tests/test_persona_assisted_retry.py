from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.persona_assisted import (
    MODEL_SHA,
    FakeProposer,
    outside_audit,
    prepared_study,
)

from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.persona_study import assisted_labels as assisted_module
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_attempts import (
    PROPOSALS_PATH,
    RETRY_LINK_PATH,
    RETRY_PROPOSALS_PATH,
)
from ynoy.persona_study.assisted_labels import (
    AssistedLabelProposalResult,
    propose_assisted_labels,
)
from ynoy.persona_study.assisted_review import (
    RETRY_QUICK_REVIEW_MARKDOWN_PATH,
    RETRY_QUICK_REVIEW_PATH,
)


def _unreliable_primary(store: PersonaStudyStore, study_id: str) -> AssistedLabelProposalResult:
    proposer = FakeProposer()
    targets = outside_audit(store, study_id, 5)
    proposer.invalid.update(
        (order, pass_name) for order in targets for pass_name in ("direct", "skeptical")
    )
    result = propose_assisted_labels(store, study_id, proposer)
    assert result.bundle.receipt.status == "unreliable"
    return result


def test_unreliable_primary_requires_explicit_retry_and_preserves_lineage(
    tmp_path: Path,
) -> None:
    store, prepared = prepared_study(tmp_path)
    study_id = prepared.manifest.study_id
    primary = _unreliable_primary(store, study_id)
    primary_bytes = store.read_artifact(study_id, PROPOSALS_PATH)
    default_second = FakeProposer()

    with pytest.raises(DataValidationError) as blocked:
        propose_assisted_labels(store, study_id, default_second)
    assert blocked.value.code == "persona_proposals_already_exist"
    assert default_second.calls == []

    retry = propose_assisted_labels(store, study_id, FakeProposer(), attempt="retry_01")

    assert retry.bundle.receipt.status == "review_ready"
    assert store.read_artifact(study_id, PROPOSALS_PATH) == primary_bytes
    assert store.read_artifact(study_id, RETRY_PROPOSALS_PATH)
    link = json.loads(store.read_artifact(study_id, RETRY_LINK_PATH))
    assert link["previous_receipt_sha256"] == primary.bundle.receipt.receipt_sha256
    assert link["retry_receipt_sha256"] == retry.bundle.receipt.receipt_sha256
    assert link["reason"] == "previous_attempt_unreliable"
    entries = {item.relative_path: item for item in store.read_index(study_id).entries}
    assert entries[PROPOSALS_PATH].mutable_by == "none"
    assert entries[RETRY_PROPOSALS_PATH].mutable_by == "none"
    assert entries[RETRY_LINK_PATH].mutable_by == "none"
    assert entries[RETRY_QUICK_REVIEW_PATH].mutable_by == "represented_user"
    assert entries[RETRY_QUICK_REVIEW_MARKDOWN_PATH].mutable_by == "none"


def test_retry_is_rejected_after_review_ready_primary(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    study_id = prepared.manifest.study_id
    propose_assisted_labels(store, study_id, FakeProposer())
    retry = FakeProposer()

    with pytest.raises(DataValidationError) as blocked:
        propose_assisted_labels(store, study_id, retry, attempt="retry_01")

    assert blocked.value.code == "persona_proposal_retry_unavailable"
    assert retry.calls == []
    assert not store.paths.artifact(study_id, RETRY_PROPOSALS_PATH).exists()


def test_second_retry_is_rejected_without_replacing_first_retry(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    study_id = prepared.manifest.study_id
    _unreliable_primary(store, study_id)
    propose_assisted_labels(store, study_id, FakeProposer(), attempt="retry_01")
    retry_bytes = store.read_artifact(study_id, RETRY_PROPOSALS_PATH)
    second = FakeProposer()

    with pytest.raises(DataValidationError) as blocked:
        propose_assisted_labels(store, study_id, second, attempt="retry_01")

    assert blocked.value.code == "persona_proposal_retry_unavailable"
    assert second.calls == []
    assert store.read_artifact(study_id, RETRY_PROPOSALS_PATH) == retry_bytes


def test_retry_cli_emits_attempt_without_private_content_or_identifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store, prepared = prepared_study(tmp_path, evaluation_time=datetime.now(UTC))
    study_id = prepared.manifest.study_id
    primary = _unreliable_primary(store, study_id)
    private_focus = assisted_module.presentations(store, study_id)[0].focus.content
    monkeypatch.setattr(
        "ynoy.cli.handlers.study_proposals.LocalPersonaProposer",
        lambda **_kwargs: FakeProposer(),
    )
    _configure_local_model(monkeypatch)

    exit_code = main(
        [
            "--indent",
            "0",
            "--private-root",
            str(store.root),
            "study",
            "propose-labels",
            study_id,
            "--synthetic",
            "--retry-unreliable",
        ]
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0 and payload["result"]["attempt"] == "retry_01"
    assert payload["result"]["private_content_emitted"] is False
    assert private_focus not in output and study_id not in output
    assert primary.bundle.receipt.receipt_sha256 not in output
    retry = json.loads(store.read_artifact(study_id, RETRY_PROPOSALS_PATH))
    assert retry["receipt"]["receipt_sha256"] not in output


def _configure_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNOY_LOCAL_REASONER_URL", "http://127.0.0.1:18100/v1/chat/completions")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_MODEL", "synthetic-persona-proposer")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_REVISION", "fixture-r1")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_ARTIFACT_SHA256", MODEL_SHA)
    monkeypatch.setenv("YNOY_LOCAL_MODEL_ATTESTED", "true")
