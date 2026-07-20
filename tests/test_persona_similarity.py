from __future__ import annotations

import pytest

from ynoy.models import DecisionLabel
from ynoy.models.persona_similarity import (
    SimilarityCase,
    SimilarityLabel,
    SimilarityPrediction,
    SimilaritySource,
    SimilaritySpec,
)
from ynoy.persona_similarity import audit_persona_similarity
from ynoy.util import sha256_text


def _bundle(*, label_count: int = 24):
    sources = tuple(
        SimilaritySource(
            source_id=f"source-{index}",
            source_sha256=sha256_text(text := f"independent source text for cluster {index}"),
            text=text,
        )
        for index in range(24)
    )
    cases = tuple(
        SimilarityCase(
            case_id=f"case-{index}",
            cluster_id=f"cluster-{index % 8}",
            prompt_sha256=sha256_text(f"prompt-{index}"),
            source_neighbor_sha256s=(),
            target_isolated=True,
            prospective=True,
        )
        for index in range(24)
    )
    predictions = tuple(
        SimilarityPrediction(
            case_id=case.case_id,
            arm=arm,
            response_text="neutral-model-answer",
            decision_label=DecisionLabel.ACCEPT,
            frozen_before_target=True,
        )
        for case in cases
        for arm in ("generic", "retrieval", "structured")
    )
    labels = tuple(
        SimilarityLabel(
            case_id=case.case_id,
            decision_label=DecisionLabel.ACCEPT,
            sealed_after_freeze=True,
            represented_user_authenticated=False,
        )
        for case in cases[:label_count]
    )
    return sources, cases, predictions, labels, SimilaritySpec()


def test_exact_copy_and_high_overlap_are_not_similarity_evidence() -> None:
    sources, cases, predictions, labels, spec = _bundle()
    duplicate = sources[1].model_copy(
        update={"text": sources[0].text, "source_sha256": sha256_text(sources[0].text)}
    )
    high_overlap_text = (
        "independent source text for cluster 0 with a long shared phrase "
        "and only one changed suffix"
    )
    high_overlap = sources[2].model_copy(
        update={"text": high_overlap_text, "source_sha256": sha256_text(high_overlap_text)}
    )
    contaminated_predictions = list(predictions)
    contaminated_predictions[2] = contaminated_predictions[2].model_copy(
        update={"response_text": sources[0].text}
    )
    contaminated_predictions[5] = contaminated_predictions[5].model_copy(
        update={"response_text": high_overlap.text}
    )
    audit = audit_persona_similarity(
        cases,
        (sources[0], duplicate, high_overlap, *sources[3:]),
        tuple(contaminated_predictions),
        labels,
        spec,
    )

    assert audit.status in {"contaminated", "inconclusive"}
    assert audit.exact_copy_case_ids or audit.contaminated_case_ids
    assert audit.persona_quality_claimed is False


def test_source_neighbor_hash_overlap_invalidates_similarity_split() -> None:
    sources, cases, predictions, labels, spec = _bundle()
    changed = cases[0].model_copy(update={"source_neighbor_sha256s": (sources[0].source_sha256,)})

    audit = audit_persona_similarity((changed, *cases[1:]), sources, predictions, labels, spec)

    assert audit.status == "invalid_target_isolation"
    assert audit.persona_quality_claimed is False


def test_insufficient_prospective_labels_is_not_a_benchmark_result() -> None:
    sources, cases, predictions, _, spec = _bundle(label_count=17)
    labels = tuple(
        SimilarityLabel(
            case_id=case.case_id,
            decision_label=DecisionLabel.ACCEPT,
            sealed_after_freeze=True,
            represented_user_authenticated=True,
        )
        for case in cases[:17]
    )

    audit = audit_persona_similarity(cases, sources, predictions, labels, spec)

    assert audit.status == "insufficient_labels"
    assert audit.eligible_case_count == 17
    assert audit.persona_quality_claimed is False


def test_complete_unverified_labels_remain_proxy_only() -> None:
    sources, cases, predictions, labels, spec = _bundle()

    audit = audit_persona_similarity(cases, sources, predictions, labels, spec)

    assert audit.status == "proxy_only"
    assert audit.prospective_authenticated_labels_used is False
    assert audit.persona_quality_claimed is False


def test_prospective_authenticated_flag_requires_prospective_cases_not_booleans_alone() -> None:
    sources, cases, predictions, _, spec = _bundle()
    non_prospective = tuple(case.model_copy(update={"prospective": False}) for case in cases)
    labels = tuple(
        SimilarityLabel(
            case_id=case.case_id,
            decision_label=DecisionLabel.ACCEPT,
            sealed_after_freeze=True,
            represented_user_authenticated=True,
        )
        for case in non_prospective
    )

    audit = audit_persona_similarity(non_prospective, sources, predictions, labels, spec)

    assert audit.status == "proxy_only"
    assert audit.prospective_authenticated_labels_used is False


def test_similarity_source_hash_must_match_its_text() -> None:
    sources, _, _, _, _ = _bundle()
    tampered = sources[0].model_copy(update={"source_sha256": "0" * 64})

    with pytest.raises(ValueError):
        SimilaritySource.model_validate(tampered.model_dump(mode="python"))
