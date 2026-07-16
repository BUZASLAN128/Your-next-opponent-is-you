from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.persona_assisted import (
    MODEL_SHA,
    PRIVATE_SENTINEL,
    FakeProposer,
    base_audit_orders,
    outside_audit,
    prepared_study,
    repeat_pair_orders,
)

from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.models import AnnotationPresentation
from ynoy.persona_study import assisted_labels as assisted_module
from ynoy.persona_study.assisted_labels import (
    PROPOSALS_PATH,
    propose_assisted_labels,
)
from ynoy.persona_study.assisted_review import QUICK_REVIEW_MARKDOWN_PATH, QUICK_REVIEW_PATH


def _review(store: object, study_id: str) -> dict[str, object]:
    raw = store.read_artifact(study_id, QUICK_REVIEW_PATH, allow_user_draft=True)
    return json.loads(raw)


def test_two_passes_run_after_deterministic_audit_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    proposer.audit_was_selected = False
    original_select = assisted_module._base_audit_ids

    def select_first(study_id: str, cards: tuple[AnnotationPresentation, ...]) -> set[str]:
        selected = original_select(study_id, cards)
        proposer.audit_was_selected = True
        return selected

    monkeypatch.setattr(assisted_module, "_base_audit_ids", select_first)
    study_id = prepared.manifest.study_id
    original_labels = store.read_artifact(
        study_id, "annotator/labels.template.json", allow_user_draft=True
    )

    result = propose_assisted_labels(store, study_id, proposer)

    assert len(proposer.calls) == 64
    assert proposer.calls[:4] == [
        (1, "direct"),
        (1, "skeptical"),
        (2, "direct"),
        (2, "skeptical"),
    ]
    receipt = result.bundle.receipt
    assert (receipt.status, receipt.required_review_count, receipt.stable_count) == (
        "review_ready",
        8,
        32,
    )
    selected = {item.order for item in result.bundle.proposals if item.selected_for_review}
    assert selected == base_audit_orders(store, study_id)
    assert all(not item.core_eligible for item in result.bundle.proposals)
    assert all(not item.automatic_core_promotion for item in result.bundle.proposals)
    assert not receipt.persona_quality_claimed and not receipt.automatic_core_promotion
    entries = {item.relative_path: item for item in store.read_index(study_id).entries}
    assert entries[PROPOSALS_PATH].mutable_by == "none"
    assert entries[QUICK_REVIEW_PATH].mutable_by == "represented_user"
    actions = _review(store, study_id)["actions"]
    assert len(actions) == 8
    assert all(item["allowed_actions"] == ["confirm", "correct", "not_mine"] for item in actions)
    assert (
        store.read_artifact(study_id, "annotator/labels.template.json", allow_user_draft=True)
        == original_labels
    )


def test_disagreement_forces_review_without_confirmable_judgment(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    study_id = prepared.manifest.study_id
    target = outside_audit(store, study_id, 1)[0]
    proposer.disagreement_orders.add(target)

    result = propose_assisted_labels(store, study_id, proposer)

    proposal = next(item for item in result.bundle.proposals if item.order == target)
    assert proposal.status == "disagreement"
    assert proposal.selected_for_review and proposal.chosen_judgment is None
    assert "model_pass_unstable" in proposal.risk_reasons
    assert result.bundle.receipt.required_review_count == 9
    action = next(item for item in _review(store, study_id)["actions"] if item["order"] == target)
    assert action["proposed_judgment"] is None
    assert action["allowed_actions"] == ["correct", "not_mine"]


def test_invalid_pass_keeps_only_reason_code_and_requires_review(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    study_id = prepared.manifest.study_id
    target = outside_audit(store, study_id, 1)[0]
    proposer.invalid.add((target, "skeptical"))

    result = propose_assisted_labels(store, study_id, proposer)

    proposal = next(item for item in result.bundle.proposals if item.order == target)
    assert proposal.status == "partial_invalid" and proposal.chosen_judgment is not None
    assert "invalid_output" in proposal.risk_reasons
    assert result.bundle.receipt.invalid_pass_count == 1
    immutable = store.read_artifact(study_id, PROPOSALS_PATH)
    assert PRIVATE_SENTINEL.encode() not in immutable


def test_oversized_focus_uses_stable_guard_and_longest_cards_are_audited(
    tmp_path: Path,
) -> None:
    store, prepared = prepared_study(tmp_path)
    study_id = prepared.manifest.study_id
    cards = assisted_module.presentations(store, study_id)
    longest = sorted(cards, key=lambda item: (-len(item.focus.content), item.presentation_id))[:2]
    proposer = FakeProposer()
    proposer.oversized_orders.add(longest[0].order)

    result = propose_assisted_labels(store, study_id, proposer)

    assert {item.order for item in longest} <= base_audit_orders(store, study_id)
    proposal = next(item for item in result.bundle.proposals if item.order == longest[0].order)
    assert proposal.status == "stable"
    assert proposal.direct is not None and proposal.skeptical is not None
    assert proposal.direct.method == proposal.skeptical.method == "deterministic_guard"
    guarded = proposal.chosen_judgment
    assert guarded is not None
    assert guarded.authorship == guarded.claim_holder == guarded.adoption == "unknown"
    assert guarded.decision == guarded.target_layer == guarded.confidence == "unknown"
    assert guarded.should_abstain and guarded.exclude_from_persona
    assert guarded.exclusion_reason == "uncertain"
    assert result.bundle.receipt.deterministic_guard_pass_count == 2
    assert result.bundle.receipt.invalid_pass_count == 0


def test_blind_repeat_mismatch_forces_both_presentations_into_review(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    study_id = prepared.manifest.study_id
    first, second = repeat_pair_orders(store, study_id)
    proposer.disagreement_orders.add(first)

    result = propose_assisted_labels(store, study_id, proposer)

    selected = {item.order for item in result.bundle.proposals if item.selected_for_review}
    assert {first, second} <= selected
    assert result.bundle.receipt.blind_repeat_disagreement_count == 1
    first_proposal = next(item for item in result.bundle.proposals if item.order == first)
    second_proposal = next(item for item in result.bundle.proposals if item.order == second)
    assert first_proposal.status == "disagreement"
    assert second_proposal.status == "stable"


def test_non_exact_typed_span_is_invalid_model_output(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    study_id = prepared.manifest.study_id
    target = outside_audit(store, study_id, 1)[0]
    proposer.bad_span.add((target, "skeptical"))

    result = propose_assisted_labels(store, study_id, proposer)

    proposal = next(item for item in result.bundle.proposals if item.order == target)
    assert proposal.status == "partial_invalid"
    assert "invalid_output" in proposal.risk_reasons
    assert result.bundle.receipt.invalid_pass_count == 1


def test_review_burden_over_cap_writes_no_review_draft(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    study_id = prepared.manifest.study_id
    targets = outside_audit(store, study_id, 5)
    proposer.invalid.update(
        (order, pass_name) for order in targets for pass_name in ("direct", "skeptical")
    )

    result = propose_assisted_labels(store, study_id, proposer)

    assert result.bundle.receipt.status == "unreliable"
    assert result.bundle.receipt.required_review_count == 13
    assert result.quick_review_path is None
    paths = {item.relative_path for item in store.read_index(study_id).entries}
    assert PROPOSALS_PATH in paths
    assert QUICK_REVIEW_PATH not in paths and QUICK_REVIEW_MARKDOWN_PATH not in paths


def test_unexpected_proposer_failure_writes_nothing(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    proposer = FakeProposer()
    proposer.unexpected.add((1, "direct"))
    study_id = prepared.manifest.study_id
    before = store.read_index(study_id)

    with pytest.raises(RuntimeError, match="unexpected proposer failure"):
        propose_assisted_labels(store, study_id, proposer)

    assert store.read_index(study_id) == before
    assert not store.paths.artifact(study_id, PROPOSALS_PATH).exists()


def test_invalid_provider_identity_is_rejected_before_any_model_call(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)

    class InvalidProvider(FakeProposer):
        @property
        def provider_evidence(self) -> object:
            return object()

    proposer = InvalidProvider()
    study_id = prepared.manifest.study_id

    with pytest.raises(DataValidationError) as blocked:
        propose_assisted_labels(store, study_id, proposer)

    assert blocked.value.code == "persona_proposer_identity_invalid"
    assert proposer.calls == []
    assert not store.paths.artifact(study_id, PROPOSALS_PATH).exists()


def test_second_proposal_run_cannot_replace_immutable_evidence(tmp_path: Path) -> None:
    store, prepared = prepared_study(tmp_path)
    study_id = prepared.manifest.study_id
    propose_assisted_labels(store, study_id, FakeProposer())
    immutable = store.read_artifact(study_id, PROPOSALS_PATH)
    second = FakeProposer()

    with pytest.raises(DataValidationError) as blocked:
        propose_assisted_labels(store, study_id, second)

    assert blocked.value.code == "persona_proposals_already_exist"
    assert second.calls == []
    assert store.read_artifact(study_id, PROPOSALS_PATH) == immutable


def test_proposal_cli_emits_counts_without_private_card_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store, prepared = prepared_study(tmp_path, evaluation_time=datetime.now(UTC))
    study_id = prepared.manifest.study_id
    private_focus = assisted_module.presentations(store, study_id)[0].focus.content
    fake = FakeProposer()
    monkeypatch.setattr(
        "ynoy.cli.handlers.study_proposals.LocalPersonaProposer", lambda **_kwargs: fake
    )
    monkeypatch.setenv("YNOY_LOCAL_REASONER_URL", "http://127.0.0.1:18100/v1/chat/completions")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_MODEL", "synthetic-persona-proposer")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_REVISION", "fixture-r1")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_ARTIFACT_SHA256", MODEL_SHA)
    monkeypatch.setenv("YNOY_LOCAL_MODEL_ATTESTED", "true")

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
        ]
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0 and payload["ok"] is True
    assert payload["result"]["private_content_emitted"] is False
    assert payload["result"]["counts"]["presentations"] == 32
    assert private_focus not in output
    assert study_id not in output
