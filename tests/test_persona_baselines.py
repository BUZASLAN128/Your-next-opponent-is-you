from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import (
    AnnotationDecision,
    DataClass,
    PersonaEvaluationCase,
    PersonaEvaluationTarget,
    PersonaHistoryEvidence,
)
from ynoy.persona_study.baselines import BASELINES, run_persona_baselines
from ynoy.util import canonical_sha256, sha256_text

_BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _history() -> tuple[PersonaHistoryEvidence, ...]:
    values = (
        ("accept", "python tests", True, True),
        ("reject", "unsafe migration", False, True),
        ("correct", "scope evidence", False, False),
        ("accept", "deterministic tests", True, True),
        ("reject", "unsafe deletion", False, True),
    )
    return tuple(
        PersonaHistoryEvidence(
            evidence_id=canonical_sha256(("evidence", index)),
            event_time=_BASE + timedelta(days=index),
            decision=AnnotationDecision(decision),
            context_sha256=sha256_text(text),
            lexical_text=text,
            source_receipts=(canonical_sha256(("history-source", index)),),
            scope_key="coding",
            declared=declared,
            persona_included=included,
        )
        for index, (decision, text, declared, included) in enumerate(values, start=1)
    )


def _cases() -> tuple[PersonaEvaluationCase, ...]:
    values = ("python test choice", "migration safety", "deletion safety")
    return tuple(
        PersonaEvaluationCase(
            case_id=canonical_sha256(("case", index)),
            event_time=_BASE + timedelta(days=30 + index),
            context_sha256=sha256_text(text),
            task_context=text,
            source_receipts=(canonical_sha256(("holdout-source", index)),),
            scope_key="coding",
            data_class=DataClass.PUBLIC_SYNTHETIC,
            synthetic=True,
        )
        for index, text in enumerate(values, start=1)
    )


def _targets(
    cases: tuple[PersonaEvaluationCase, ...],
) -> tuple[PersonaEvaluationTarget, ...]:
    decisions = (
        AnnotationDecision.ACCEPT,
        AnnotationDecision.REJECT,
        AnnotationDecision.REJECT,
    )
    return tuple(
        PersonaEvaluationTarget(
            case_id=case.case_id,
            decision=decision,
            authority="synthetic_fixture",
        )
        for case, decision in zip(cases, decisions, strict=True)
    )


def _run(
    cases: tuple[PersonaEvaluationCase, ...] | None = None,
    history: tuple[PersonaHistoryEvidence, ...] | None = None,
    targets: tuple[PersonaEvaluationTarget, ...] | None = None,
):
    selected_cases = cases or _cases()
    return run_persona_baselines(
        selected_cases,
        history or _history(),
        targets or _targets(selected_cases),
        holdout_freeze_sha256=canonical_sha256("holdout-freeze"),
        deletion_proof_id=canonical_sha256("deletion-proof"),
        retention_expires_at=_BASE + timedelta(days=40),
    )


def test_zero_low_and_history_baselines_report_abstention_and_provenance() -> None:
    run = _run()

    assert run.case_count == run.target_count == 3
    assert run.protected_holdout is True
    assert run.duplicate_case_count == run.exact_training_overlap_count == 0
    assert run.model_provider_used is False and run.automatic_core_promotion is False
    assert run.persona_quality_claimed is False
    assert run.evidence_tier == "mock/support"
    assert set(run.metrics) == set(BASELINES)
    assert run.metrics["zero_abstain"]["coverage"] == 0.0
    assert run.metrics["zero_abstain"]["abstention_rate"] == 1.0
    assert any(run.metrics[name]["coverage"] > 0 for name in BASELINES[1:])
    assert all(values["provenance_completeness"] == 1.0 for values in run.metrics.values())


def test_targets_never_change_predictor_outputs() -> None:
    cases = _cases()
    first = _run(cases=cases)
    changed = tuple(
        item.model_copy(update={"decision": AnnotationDecision.ASK}) for item in _targets(cases)
    )
    second = _run(cases=cases, targets=changed)

    assert first.predictions == second.predictions
    assert first.metrics != second.metrics


def test_future_and_wrong_scope_history_are_not_used() -> None:
    future = _history()[0].model_copy(
        update={
            "evidence_id": canonical_sha256("future"),
            "event_time": _BASE + timedelta(days=90),
            "decision": AnnotationDecision.ASK,
            "source_receipts": (canonical_sha256("future-source"),),
        }
    )
    wrong_scope = _history()[0].model_copy(
        update={
            "evidence_id": canonical_sha256("wrong-scope"),
            "scope_key": "other",
            "decision": AnnotationDecision.ASK,
            "source_receipts": (canonical_sha256("wrong-scope-source"),),
        }
    )

    run = _run(history=(*_history(), future, wrong_scope))
    frequency = tuple(item for item in run.predictions if item.baseline == "history_frequency")

    assert all(item.predicted_decision != AnnotationDecision.ASK for item in frequency)
    assert all(future.evidence_id not in item.evidence_receipts for item in frequency)
    assert all(wrong_scope.evidence_id not in item.evidence_receipts for item in frequency)


@pytest.mark.parametrize("kind", ["history", "case"])
def test_context_receipt_must_match_exact_text(kind: str) -> None:
    value = _history()[0] if kind == "history" else _cases()[0]
    payload = value.model_dump(mode="python")
    payload["context_sha256"] = canonical_sha256(("fake-context", kind))
    model = PersonaHistoryEvidence if kind == "history" else PersonaEvaluationCase

    with pytest.raises(ValidationError, match="receipt does not match"):
        model.model_validate(payload)


@pytest.mark.parametrize("overlap_kind", ["duplicate_case", "content", "source"])
def test_duplicate_or_training_overlap_fails_closed(overlap_kind: str) -> None:
    cases = list(_cases())
    history = list(_history())
    if overlap_kind == "duplicate_case":
        cases[1] = cases[1].model_copy(
            update={
                "task_context": cases[0].task_context,
                "context_sha256": cases[0].context_sha256,
            }
        )
        expected = "persona_baseline_duplicate_holdout"
    elif overlap_kind == "content":
        history[0] = history[0].model_copy(
            update={
                "lexical_text": cases[0].task_context,
                "context_sha256": cases[0].context_sha256,
            }
        )
        expected = "persona_baseline_training_content_overlap"
    else:
        history[0] = history[0].model_copy(update={"source_receipts": cases[0].source_receipts})
        expected = "persona_baseline_training_source_overlap"

    with pytest.raises(DataValidationError) as error:
        _run(cases=tuple(cases), history=tuple(history))

    assert error.value.code == expected
