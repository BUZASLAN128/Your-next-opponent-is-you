from __future__ import annotations

import re
from collections import defaultdict

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models.persona_similarity import (
    PersonaSimilarityAudit,
    SimilarityArm,
    SimilarityCase,
    SimilarityLabel,
    SimilarityPrediction,
    SimilaritySource,
    SimilaritySpec,
    SimilarityStatus,
)
from ynoy.util import canonical_sha256

_ARMS: tuple[SimilarityArm, ...] = ("generic", "retrieval", "structured")
_TOKEN = re.compile(r"[\wçğıöşü]+", re.IGNORECASE)  # noqa: RUF001


def audit_persona_similarity(
    cases: tuple[SimilarityCase, ...],
    source_texts: tuple[SimilaritySource, ...],
    predictions: tuple[SimilarityPrediction, ...],
    labels: tuple[SimilarityLabel, ...],
    spec: SimilaritySpec,
) -> PersonaSimilarityAudit:
    """Audit target isolation, copying, and decision agreement without claiming fidelity."""
    safe_cases, safe_sources, safe_predictions, safe_labels, safe_spec = _validated_inputs(
        cases, source_texts, predictions, labels, spec
    )
    prediction_map = {(item.case_id, item.arm): item for item in safe_predictions}
    label_map = {item.case_id: item for item in safe_labels}
    eligible = _eligible_cases(safe_cases, prediction_map, label_map)
    isolation_valid = _target_isolation_valid(safe_cases, safe_sources, safe_predictions)
    overlaps, contaminated, exact = _copy_diagnostics(
        eligible, safe_sources, prediction_map, safe_spec
    )
    accuracy = _decision_accuracy(eligible, prediction_map, label_map)
    # V0.1 labels carry no independently validated signature/freeze receipt.
    # Caller-authored booleans therefore remain proxy evidence by construction.
    authenticated = False
    status, reason = _status(
        eligible,
        safe_spec,
        isolation_valid=isolation_valid,
        contaminated=contaminated,
        authenticated=authenticated,
    )
    payload: dict[str, object] = {
        "protocol_version": "persona-similarity-audit/0.1",
        "status": status,
        "reason": reason,
        "eligible_case_count": len(eligible),
        "cluster_count": len({item.cluster_id for item in eligible}),
        "contaminated_case_ids": tuple(sorted(contaminated)),
        "exact_copy_case_ids": tuple(sorted(exact)),
        "max_source_overlap": overlaps,
        "arm_decision_accuracy": accuracy,
        "prospective_authenticated_labels_used": authenticated,
        "persona_quality_claimed": False,
    }
    payload["audit_sha256"] = canonical_sha256(payload)
    return PersonaSimilarityAudit.model_validate(payload)


def max_source_ngram_overlap(text: str, sources: tuple[str, ...], *, ngram_size: int = 5) -> float:
    """Return symmetric containment so embedding a source passage remains detectable."""
    tokens = _tokens(text)
    return max(
        (_ngram_containment(tokens, _tokens(source), ngram_size) for source in sources),
        default=0.0,
    )


def _eligible_cases(
    cases: tuple[SimilarityCase, ...],
    predictions: dict[tuple[str, SimilarityArm], SimilarityPrediction],
    labels: dict[str, SimilarityLabel],
) -> tuple[SimilarityCase, ...]:
    return tuple(
        case
        for case in cases
        if case.case_id in labels and all((case.case_id, arm) in predictions for arm in _ARMS)
    )


def _validated_inputs(
    cases: tuple[SimilarityCase, ...],
    sources: tuple[SimilaritySource, ...],
    predictions: tuple[SimilarityPrediction, ...],
    labels: tuple[SimilarityLabel, ...],
    spec: SimilaritySpec,
) -> tuple[
    tuple[SimilarityCase, ...],
    tuple[SimilaritySource, ...],
    tuple[SimilarityPrediction, ...],
    tuple[SimilarityLabel, ...],
    SimilaritySpec,
]:
    try:
        safe_cases = tuple(SimilarityCase.model_validate(item.model_dump()) for item in cases)
        safe_sources = tuple(SimilaritySource.model_validate(item.model_dump()) for item in sources)
        safe_predictions = tuple(
            SimilarityPrediction.model_validate(item.model_dump()) for item in predictions
        )
        safe_labels = tuple(SimilarityLabel.model_validate(item.model_dump()) for item in labels)
        safe_spec = SimilaritySpec.model_validate(spec.model_dump())
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "persona_similarity_input_invalid", "Persona similarity input is invalid."
        ) from exc
    case_ids = {item.case_id for item in safe_cases}
    prediction_keys = {(item.case_id, item.arm) for item in safe_predictions}
    invalid = (
        len(case_ids) != len(safe_cases)
        or len({item.source_id for item in safe_sources}) != len(safe_sources)
        or len(prediction_keys) != len(safe_predictions)
        or len({item.case_id for item in safe_labels}) != len(safe_labels)
        or any(item.case_id not in case_ids for item in safe_predictions)
        or any(item.case_id not in case_ids for item in safe_labels)
    )
    if invalid:
        raise DataValidationError(
            "persona_similarity_binding_invalid", "Persona similarity bindings are invalid."
        )
    return safe_cases, safe_sources, safe_predictions, safe_labels, safe_spec


def _target_isolation_valid(
    cases: tuple[SimilarityCase, ...],
    sources: tuple[SimilaritySource, ...],
    predictions: tuple[SimilarityPrediction, ...],
) -> bool:
    source_hashes = {item.source_sha256 for item in sources}
    return (
        all(item.target_isolated for item in cases)
        and all(not (set(item.source_neighbor_sha256s) & source_hashes) for item in cases)
        and all(item.frozen_before_target and not item.target_seen for item in predictions)
    )


def _copy_diagnostics(
    cases: tuple[SimilarityCase, ...],
    sources: tuple[SimilaritySource, ...],
    predictions: dict[tuple[str, SimilarityArm], SimilarityPrediction],
    spec: SimilaritySpec,
) -> tuple[dict[SimilarityArm, float], set[str], set[str]]:
    source_texts = tuple(item.text for item in sources)
    normalized_sources = tuple(_tokens(text) for text in source_texts)
    maximum = {arm: 0.0 for arm in _ARMS}
    contaminated: set[str] = set()
    exact: set[str] = set()
    source_sequences = {tokens for tokens in normalized_sources if tokens}
    for case in cases:
        for arm in _ARMS:
            tokens = _tokens(predictions[(case.case_id, arm)].response_text)
            overlap = max_source_ngram_overlap(
                predictions[(case.case_id, arm)].response_text,
                source_texts,
                ngram_size=spec.ngram_size,
            )
            maximum[arm] = max(maximum[arm], overlap)
            if arm == "structured" and tokens in source_sequences:
                exact.add(case.case_id)
            if arm == "structured" and overlap > spec.max_source_overlap:
                contaminated.add(case.case_id)
    return maximum, contaminated, exact


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN.findall(text))


def _ngram_containment(left: tuple[str, ...], right: tuple[str, ...], size: int) -> float:
    if not left or not right:
        return 0.0
    if len(left) < size or len(right) < size:
        overlap = set(left) & set(right)
        return len(overlap) / min(len(set(left)), len(set(right)))
    left_grams = {left[index : index + size] for index in range(len(left) - size + 1)}
    right_grams = {right[index : index + size] for index in range(len(right) - size + 1)}
    return len(left_grams & right_grams) / min(len(left_grams), len(right_grams))


def _decision_accuracy(
    cases: tuple[SimilarityCase, ...],
    predictions: dict[tuple[str, SimilarityArm], SimilarityPrediction],
    labels: dict[str, SimilarityLabel],
) -> dict[SimilarityArm, float | None]:
    correct: dict[SimilarityArm, int] = defaultdict(int)
    for case in cases:
        for arm in _ARMS:
            correct[arm] += int(
                predictions[(case.case_id, arm)].decision_label
                == labels[case.case_id].decision_label
            )
    return {arm: (correct[arm] / len(cases) if cases else None) for arm in _ARMS}


def _status(
    cases: tuple[SimilarityCase, ...],
    spec: SimilaritySpec,
    *,
    isolation_valid: bool,
    contaminated: set[str],
    authenticated: bool,
) -> tuple[SimilarityStatus, str]:
    if not isolation_valid:
        return "invalid_target_isolation", "Prediction or source isolation is invalid."
    if len(cases) < spec.minimum_cases or len({item.cluster_id for item in cases}) < (
        spec.minimum_clusters
    ):
        return "insufficient_labels", "Prospective label or cluster support is insufficient."
    if contaminated:
        return "contaminated", "Structured responses exceed the frozen source-overlap limit."
    if not authenticated:
        return "proxy_only", "Labels are not authenticated represented-user judgments."
    return "inconclusive", "Authenticated evidence exists but no superiority claim is defined."
