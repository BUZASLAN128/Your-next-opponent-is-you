from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, cast

from ynoy.errors import DataValidationError
from ynoy.models import (
    AnnotationDecision,
    PersonaBaselinePrediction,
    PersonaBaselineRun,
    PersonaEvaluationCase,
    PersonaEvaluationTarget,
    PersonaHistoryEvidence,
)
from ynoy.models.persona_evaluation import PersonaBaselineName
from ynoy.util import canonical_sha256

BASELINES: tuple[PersonaBaselineName, ...] = (
    "zero_abstain",
    "low_recent3",
    "history_frequency",
    "history_lexical",
    "history_declared",
    "history_structured",
)
_SCORABLE = frozenset(
    {
        AnnotationDecision.ACCEPT,
        AnnotationDecision.REJECT,
        AnnotationDecision.CORRECT,
        AnnotationDecision.DEFER,
        AnnotationDecision.ASK,
    }
)


def run_persona_baselines(
    cases: Sequence[PersonaEvaluationCase],
    history: Sequence[PersonaHistoryEvidence],
    targets: Sequence[PersonaEvaluationTarget],
    *,
    holdout_freeze_sha256: str,
    deletion_proof_id: str,
    retention_expires_at: datetime,
) -> PersonaBaselineRun:
    _validate_inputs(cases, history, targets)
    predictions = tuple(
        _predict(case, baseline, history) for baseline in BASELINES for case in cases
    )
    target_map = {item.case_id: item.decision for item in targets}
    metrics = {
        baseline: _metrics(
            tuple(item for item in predictions if item.baseline == baseline), target_map
        )
        for baseline in BASELINES
    }
    payload = {
        "holdout_freeze_sha256": holdout_freeze_sha256,
        "deletion_proof_id": deletion_proof_id,
        "retention_expires_at": retention_expires_at,
        "case_count": len(cases),
        "target_count": len(targets),
        "predictions": predictions,
        "metrics": metrics,
        "target_authority": targets[0].authority,
        "evidence_tier": "mock/support" if cases[0].synthetic else "live",
    }
    draft = cast(Any, PersonaBaselineRun).model_construct(**payload, run_sha256="0" * 64)
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"run_sha256"}))
    return PersonaBaselineRun.model_validate({**payload, "run_sha256": digest})


def _validate_inputs(
    cases: Sequence[PersonaEvaluationCase],
    history: Sequence[PersonaHistoryEvidence],
    targets: Sequence[PersonaEvaluationTarget],
) -> None:
    case_ids = tuple(item.case_id for item in cases)
    target_ids = tuple(item.case_id for item in targets)
    if not cases or not history or case_ids != target_ids or len(set(case_ids)) != len(case_ids):
        raise DataValidationError(
            "persona_baseline_case_target_mismatch",
            "Baseline cases and targets must be non-empty, unique, and ordered identically.",
        )
    if len({item.authority for item in targets}) != 1:
        raise DataValidationError(
            "persona_baseline_target_authority_mixed", "Target authority must be uniform."
        )
    case_contexts = [item.context_sha256 for item in cases]
    case_sources = {receipt for item in cases for receipt in item.source_receipts}
    history_sources = {receipt for item in history for receipt in item.source_receipts}
    if len(case_contexts) != len(set(case_contexts)):
        raise DataValidationError(
            "persona_baseline_duplicate_holdout", "Duplicate holdout contexts are not scored."
        )
    if set(case_contexts) & {item.context_sha256 for item in history}:
        raise DataValidationError(
            "persona_baseline_training_content_overlap", "Exact training content entered holdout."
        )
    if case_sources & history_sources:
        raise DataValidationError(
            "persona_baseline_training_source_overlap", "A training source entered holdout."
        )


def _predict(
    case: PersonaEvaluationCase,
    baseline: PersonaBaselineName,
    history: Sequence[PersonaHistoryEvidence],
) -> PersonaBaselinePrediction:
    eligible = tuple(
        item
        for item in history
        if item.event_time < case.event_time
        and (item.scope_key is None or item.scope_key == case.scope_key)
        and item.decision in _SCORABLE
    )
    decision, receipts = _PREDICTORS[baseline](case, eligible)
    abstained = decision == AnnotationDecision.UNKNOWN
    return PersonaBaselinePrediction(
        case_id=case.case_id,
        baseline=baseline,
        predicted_decision=decision,
        confidence=0.0 if abstained else 0.6,
        abstained=abstained,
        evidence_receipts=receipts,
        unknowns=("represented_user_decision",) if abstained else (),
        provenance_complete=abstained or bool(receipts),
    )


Predictor = Callable[
    [PersonaEvaluationCase, Sequence[PersonaHistoryEvidence]],
    tuple[AnnotationDecision, tuple[str, ...]],
]


def _zero(
    case: PersonaEvaluationCase, history: Sequence[PersonaHistoryEvidence]
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    del case, history
    return AnnotationDecision.UNKNOWN, ()


def _recent(
    case: PersonaEvaluationCase, history: Sequence[PersonaHistoryEvidence]
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    del case
    selected = sorted(history, key=lambda item: (item.event_time, item.evidence_id))[-3:]
    return _from_evidence(selected)


def _frequency(
    case: PersonaEvaluationCase, history: Sequence[PersonaHistoryEvidence]
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    del case
    return _from_evidence(history)


def _lexical(
    case: PersonaEvaluationCase, history: Sequence[PersonaHistoryEvidence]
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    tokens = _tokens(case.task_context)
    ranked = sorted(
        history,
        key=lambda item: (-len(tokens & _tokens(item.lexical_text)), item.evidence_id),
    )
    return _from_evidence(ranked[:1])


def _declared(
    case: PersonaEvaluationCase, history: Sequence[PersonaHistoryEvidence]
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    del case
    return _from_evidence(tuple(item for item in history if item.declared))


def _structured(
    case: PersonaEvaluationCase, history: Sequence[PersonaHistoryEvidence]
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    del case
    return _from_evidence(tuple(item for item in history if item.persona_included))


def _from_evidence(
    values: Sequence[PersonaHistoryEvidence],
) -> tuple[AnnotationDecision, tuple[str, ...]]:
    if not values:
        return AnnotationDecision.UNKNOWN, ()
    counts = Counter(item.decision for item in values)
    decision = sorted(counts, key=lambda item: (-counts[item], item.value))[0]
    return decision, tuple(item.evidence_id for item in values)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[\w-]+", value.casefold()))


def _metrics(
    predictions: tuple[PersonaBaselinePrediction, ...],
    targets: dict[str, AnnotationDecision],
) -> dict[str, float | int]:
    covered = tuple(item for item in predictions if not item.abstained)
    correct = sum(item.predicted_decision == targets[item.case_id] for item in covered)
    total = len(predictions)
    return {
        "total": total,
        "covered": len(covered),
        "correct": correct,
        "coverage": len(covered) / total,
        "selective_accuracy": correct / len(covered) if covered else 0.0,
        "abstention_rate": (total - len(covered)) / total,
        "provenance_completeness": sum(item.provenance_complete for item in predictions) / total,
    }


_PREDICTORS: dict[PersonaBaselineName, Predictor] = {
    "zero_abstain": _zero,
    "low_recent3": _recent,
    "history_frequency": _frequency,
    "history_lexical": _lexical,
    "history_declared": _declared,
    "history_structured": _structured,
}
