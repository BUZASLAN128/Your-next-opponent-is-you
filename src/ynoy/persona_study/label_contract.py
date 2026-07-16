from __future__ import annotations

from collections import defaultdict
from typing import Any, cast

from pydantic import TypeAdapter, ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import (
    AnnotationPresentation,
    BlindMapEntry,
    CompletedPersonaLabelSet,
    DataClass,
    PersonaAnnotationJudgment,
    PersonaAnnotationLabel,
    PersonaInitialLabelReceipt,
    PersonaLabelSealReceipt,
    SealedPersonaLabel,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.render import label_template
from ynoy.util import canonical_sha256, sha256_bytes

LABEL_PATH = "annotator/labels.template.json"
PRESENTATIONS_PATH = "annotator/presentations.json"
BLIND_MAP_PATH = "evaluator/blind-map.json"
INITIAL_LABELS_PATH = "evaluator/labels.initial.json"
INITIAL_RECEIPT_PATH = "evaluator/repeat-agreement.initial.json"
ADJUDICATION_PATH = "annotator/repeat-adjudication.template.json"
SEALED_LABELS_PATH = "evaluator/labels.sealed.json"
SEAL_RECEIPT_PATH = "evaluator/label-seal.json"
AGREEMENT_FIELDS = (
    "authorship",
    "claim_holder",
    "adoption",
    "decision",
    "target_layer",
    "persona_kind",
    "scope",
    "rationale_spans",
    "evidence_demand_spans",
    "should_abstain",
    "exclude_from_persona",
    "exclusion_reason",
    "confidence",
)


def presentations(store: PersonaStudyStore, study_id: str) -> tuple[AnnotationPresentation, ...]:
    return cast(
        tuple[AnnotationPresentation, ...],
        _typed_artifact(store, study_id, PRESENTATIONS_PATH, tuple[AnnotationPresentation, ...]),
    )


def blind_map(store: PersonaStudyStore, study_id: str) -> tuple[BlindMapEntry, ...]:
    return cast(
        tuple[BlindMapEntry, ...],
        _typed_artifact(store, study_id, BLIND_MAP_PATH, tuple[BlindMapEntry, ...]),
    )


def completed_labels(store: PersonaStudyStore, study_id: str) -> CompletedPersonaLabelSet:
    return completed_labels_with_digest(store, study_id)[0]


def completed_labels_with_digest(
    store: PersonaStudyStore, study_id: str
) -> tuple[CompletedPersonaLabelSet, str]:
    raw = store.read_artifact(study_id, LABEL_PATH, allow_user_draft=True)
    try:
        return CompletedPersonaLabelSet.model_validate_json(raw), sha256_bytes(raw)
    except ValidationError as exc:
        raise DataValidationError(
            "persona_labels_incomplete_or_invalid",
            "Every label must be completed by the represented user using the allowed values.",
        ) from exc


def initial_labels(store: PersonaStudyStore, study_id: str) -> CompletedPersonaLabelSet:
    try:
        return CompletedPersonaLabelSet.model_validate_json(
            store.read_artifact(study_id, INITIAL_LABELS_PATH)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_initial_labels_invalid", "The immutable initial label submission is invalid."
        ) from exc


def validate_completed_labels(
    completed: CompletedPersonaLabelSet,
    cards: tuple[AnnotationPresentation, ...],
    mapping: tuple[BlindMapEntry, ...],
) -> None:
    expected = label_template(completed.study_id, cards)
    expected_ids = tuple(item.presentation_id for item in cards)
    expected_instructions = cast(list[str], expected["instructions"])
    expected_catalog = cast(dict[str, list[str]], expected["allowed_values"])
    expected_allowed = {key: tuple(value) for key, value in expected_catalog.items()}
    label_ids = tuple(item.presentation_id for item in completed.labels)
    blind_ids = tuple(item.presentation_id for item in mapping)
    if (
        tuple(expected_instructions) != completed.instructions
        or expected_allowed != completed.allowed_values
    ):
        raise DataValidationError(
            "persona_labels_contract_changed", "The represented-user label contract changed."
        )
    if expected_ids != label_ids or expected_ids != blind_ids:
        raise DataValidationError(
            "persona_labels_presentation_mismatch",
            "Completed labels do not match the immutable presentation order.",
        )
    focus_by_id = {item.presentation_id: item.focus.content for item in cards}
    for label in completed.labels:
        validate_judgment_spans(label, focus_by_id[label.presentation_id])


def repeat_groups(
    cards: tuple[AnnotationPresentation, ...], mapping: tuple[BlindMapEntry, ...]
) -> dict[str, tuple[BlindMapEntry, ...]]:
    order = {item.presentation_id: item.order for item in cards}
    grouped: dict[str, list[BlindMapEntry]] = defaultdict(list)
    for entry in mapping:
        grouped[entry.window_id].append(entry)
    pairs = tuple(group for group in grouped.values() if len(group) == 2)
    singles = tuple(group for group in grouped.values() if len(group) == 1)
    pair_flags = all(sum(item.repeated for item in group) == 1 for group in pairs)
    single_flags = all(not group[0].repeated for group in singles)
    if (
        len(grouped) != 24
        or len(pairs) != 8
        or len(singles) != 16
        or not pair_flags
        or not single_flags
    ):
        raise DataValidationError(
            "persona_label_repeat_shape_invalid", "The immutable blind-repeat shape is invalid."
        )
    return {
        key: tuple(sorted(values, key=lambda item: order[item.presentation_id]))
        for key, values in grouped.items()
    }


def validate_judgment_spans(judgment: PersonaAnnotationJudgment, focus: str) -> None:
    spans = (*judgment.rationale_spans, *judgment.evidence_demand_spans)
    if any(span.end > len(focus) or focus[span.start : span.end] != span.text for span in spans):
        raise DataValidationError(
            "persona_label_span_mismatch", "A label span is not exact focus text."
        )


def judgment(label: PersonaAnnotationLabel) -> PersonaAnnotationJudgment:
    return PersonaAnnotationJudgment.model_validate(
        label.model_dump(mode="python", exclude={"presentation_id"})
    )


def sealed_label(
    window_id: str,
    entries: tuple[BlindMapEntry, ...],
    value: PersonaAnnotationJudgment,
) -> SealedPersonaLabel:
    partitions = {item.annotation_partition for item in entries}
    if len(partitions) != 1:
        raise DataValidationError(
            "persona_label_partition_leakage", "One window crossed annotation partitions."
        )
    return SealedPersonaLabel(
        window_id=window_id,
        annotation_partition=partitions.pop(),
        source_presentation_ids=tuple(item.presentation_id for item in entries),
        judgment=value,
    )


def final_receipt(
    completed: CompletedPersonaLabelSet,
    labels: tuple[SealedPersonaLabel, ...],
    initial: PersonaInitialLabelReceipt,
    adjudicated_count: int,
    adjudication_set_sha256: str | None = None,
) -> PersonaLabelSealReceipt:
    payload = {
        "study_id": completed.study_id,
        "label_set_sha256": canonical_sha256([item.model_dump(mode="json") for item in labels]),
        "initial_submission_receipt_sha256": initial.receipt_sha256,
        "initial_repeat_exact_match_count": initial.repeat_exact_match_count,
        "adjudicated_repeat_pair_count": adjudicated_count,
        "adjudication_set_sha256": adjudication_set_sha256,
        "initial_field_agreement_counts": initial.field_agreement_counts,
        "excluded_from_persona_count": sum(item.judgment.exclude_from_persona for item in labels),
        "abstained_count": sum(item.judgment.should_abstain for item in labels),
        "persona_candidate_count": sum(
            not item.judgment.exclude_from_persona and item.judgment.target_layer.value == "persona"
            for item in labels
        ),
    }
    draft = cast(Any, PersonaLabelSealReceipt).model_construct(**payload, receipt_sha256="0" * 64)
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"receipt_sha256"}))
    return PersonaLabelSealReceipt.model_validate({**payload, "receipt_sha256": digest})


def derived_class(index: StudyArtifactIndex) -> DataClass:
    return (
        DataClass.PUBLIC_SYNTHETIC
        if all(item.data_class == DataClass.PUBLIC_SYNTHETIC for item in index.entries)
        else DataClass.DERIVED_IDENTITY
    )


def dependencies(index: StudyArtifactIndex) -> tuple[str, ...]:
    return tuple(sorted({value for entry in index.entries for value in entry.source_dependencies}))


def has_entry(
    index: StudyArtifactIndex, relative_path: str, *, mutable: bool | None = None
) -> bool:
    matches = tuple(item for item in index.entries if item.relative_path == relative_path)
    if len(matches) != 1:
        return False
    return mutable is None or (matches[0].mutable_by != "none") == mutable


def _typed_artifact(store: PersonaStudyStore, study_id: str, relative: str, annotation: Any) -> Any:
    try:
        return TypeAdapter(annotation).validate_json(store.read_artifact(study_id, relative))
    except ValidationError as exc:
        raise DataValidationError(
            "persona_study_artifact_invalid", "An immutable persona-study artifact is invalid."
        ) from exc
