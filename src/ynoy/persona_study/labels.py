from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import (
    AnnotationPresentation,
    BlindMapEntry,
    CompletedPersonaLabelSet,
    CompletedRepeatAdjudicationSet,
    PersonaAnnotationJudgment,
    PersonaInitialLabelReceipt,
    PersonaLabelSealReceipt,
    SealedPersonaLabel,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.label_contract import (
    ADJUDICATION_PATH,
    INITIAL_RECEIPT_PATH,
    SEAL_RECEIPT_PATH,
    SEALED_LABELS_PATH,
    blind_map,
    dependencies,
    derived_class,
    final_receipt,
    has_entry,
    initial_labels,
    judgment,
    presentations,
    repeat_groups,
    sealed_label,
    validate_completed_labels,
    validate_judgment_spans,
)
from ynoy.persona_study.label_submission import adjudication_instructions, submit_persona_labels
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes


@dataclass(frozen=True, slots=True)
class SealedPersonaLabels:
    receipt: PersonaLabelSealReceipt
    labels: tuple[SealedPersonaLabel, ...]
    artifact_index: StudyArtifactIndex


def seal_persona_labels(store: PersonaStudyStore, study_id: str) -> SealedPersonaLabels:
    index = store.read_index(study_id)
    if has_entry(index, SEALED_LABELS_PATH) and has_entry(index, SEAL_RECEIPT_PATH):
        return _load_sealed(store, study_id, index)
    if has_entry(index, "annotator/labels.template.json", mutable=True):
        submitted = submit_persona_labels(store, study_id)
        if submitted.seal_receipt is not None:
            return SealedPersonaLabels(
                submitted.seal_receipt, submitted.sealed_labels, submitted.artifact_index
            )
        raise DataValidationError(
            "persona_label_adjudication_required",
            "Initial blind-repeat mismatches were preserved; complete the adjudication draft.",
            details={"repeat_pair_mismatch_count": submitted.initial_receipt.repeat_mismatch_count},
        )
    initial = _initial_receipt(store, study_id)
    if not initial.adjudication_required:
        raise DataValidationError(
            "persona_label_seal_incomplete", "A completed initial submission is missing its seal."
        )
    return _seal_adjudication(store, study_id, index, initial)


def _seal_adjudication(
    store: PersonaStudyStore,
    study_id: str,
    index: StudyArtifactIndex,
    initial: PersonaInitialLabelReceipt,
) -> SealedPersonaLabels:
    completed = initial_labels(store, study_id)
    if initial.label_set_sha256 != canonical_sha256(completed.model_dump(mode="json")):
        raise DataValidationError(
            "persona_initial_receipt_label_mismatch",
            "The initial receipt does not bind the immutable initial labels.",
        )
    cards = presentations(store, study_id)
    mapping = blind_map(store, study_id)
    validate_completed_labels(completed, cards, mapping)
    groups = repeat_groups(cards, mapping)
    adjudication, adjudication_draft_sha256 = _completed_adjudication(store, study_id)
    decisions = _validate_adjudication(adjudication, initial, completed, cards, groups)
    label_by_id = {item.presentation_id: item for item in completed.labels}
    labels = tuple(
        sealed_label(
            window_id,
            entries,
            decisions.get(window_id, judgment(label_by_id[entries[0].presentation_id])),
        )
        for window_id, entries in sorted(groups.items())
    )
    receipt = final_receipt(
        completed,
        labels,
        initial,
        len(decisions),
        canonical_sha256(adjudication.model_dump(mode="json")),
    )
    return _persist_adjudication(store, study_id, index, labels, receipt, adjudication_draft_sha256)


def _persist_adjudication(
    store: PersonaStudyStore,
    study_id: str,
    index: StudyArtifactIndex,
    labels: tuple[SealedPersonaLabel, ...],
    receipt: PersonaLabelSealReceipt,
    adjudication_draft_sha256: str,
) -> SealedPersonaLabels:
    data_class = derived_class(index)
    source_dependencies = dependencies(index)
    payloads = (
        ArtifactPayload(
            SEALED_LABELS_PATH,
            canonical_json_bytes([item.model_dump(mode="json") for item in labels]),
            data_class,
            source_dependencies,
        ),
        ArtifactPayload(
            SEAL_RECEIPT_PATH,
            canonical_json_bytes(receipt.model_dump(mode="json")),
            data_class,
            source_dependencies,
        ),
    )
    updated = store.seal_mutable_artifact(
        study_id,
        ADJUDICATION_PATH,
        payloads,
        expected_mutable_sha256=adjudication_draft_sha256,
    )
    return SealedPersonaLabels(receipt, labels, updated)


def _validate_adjudication(
    value: CompletedRepeatAdjudicationSet,
    initial: PersonaInitialLabelReceipt,
    completed: CompletedPersonaLabelSet,
    cards: tuple[AnnotationPresentation, ...],
    groups: dict[str, tuple[BlindMapEntry, ...]],
) -> dict[str, PersonaAnnotationJudgment]:
    if value.study_id != initial.study_id or value.initial_receipt_sha256 != initial.receipt_sha256:
        raise DataValidationError(
            "persona_label_adjudication_receipt_mismatch",
            "Repeat adjudication does not match the immutable initial submission.",
        )
    if value.instructions != adjudication_instructions(value.schema_version):
        raise DataValidationError(
            "persona_label_adjudication_contract_changed",
            "The represented-user adjudication instructions changed.",
        )
    expected = {item.window_id for item in initial.pair_results if not item.exact_match}
    actual = {item.window_id for item in value.adjudications}
    if expected != actual:
        raise DataValidationError(
            "persona_label_adjudication_scope_mismatch",
            "Repeat adjudication must cover exactly the initial mismatches.",
        )
    label_by_id = {item.presentation_id: item for item in completed.labels}
    focus_by_id = {item.presentation_id: item.focus.content for item in cards}
    decisions: dict[str, PersonaAnnotationJudgment] = {}
    for item in value.adjudications:
        entries = groups[item.window_id]
        ids = tuple(entry.presentation_id for entry in entries)
        originals = tuple(judgment(label_by_id[identifier]) for identifier in ids)
        if item.source_presentation_ids != ids or item.initial_judgments != originals:
            raise DataValidationError(
                "persona_label_adjudication_initial_changed",
                "Repeat adjudication cannot rewrite the immutable initial judgments.",
            )
        validate_judgment_spans(item.final_judgment, focus_by_id[ids[0]])
        decisions[item.window_id] = item.final_judgment
    return decisions


def _completed_adjudication(
    store: PersonaStudyStore, study_id: str
) -> tuple[CompletedRepeatAdjudicationSet, str]:
    raw = store.read_artifact(study_id, ADJUDICATION_PATH, allow_user_draft=True)
    try:
        return CompletedRepeatAdjudicationSet.model_validate_json(raw), sha256_bytes(raw)
    except ValidationError as exc:
        raise DataValidationError(
            "persona_label_adjudication_incomplete",
            "Every initial repeat mismatch requires represented-user adjudication.",
        ) from exc


def _initial_receipt(store: PersonaStudyStore, study_id: str) -> PersonaInitialLabelReceipt:
    try:
        return PersonaInitialLabelReceipt.model_validate_json(
            store.read_artifact(study_id, INITIAL_RECEIPT_PATH)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_initial_receipt_invalid", "The immutable initial repeat receipt is invalid."
        ) from exc


def _load_sealed(
    store: PersonaStudyStore, study_id: str, index: StudyArtifactIndex
) -> SealedPersonaLabels:
    try:
        labels = TypeAdapter(tuple[SealedPersonaLabel, ...]).validate_json(
            store.read_artifact(study_id, SEALED_LABELS_PATH)
        )
        receipt = PersonaLabelSealReceipt.model_validate_json(
            store.read_artifact(study_id, SEAL_RECEIPT_PATH)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_label_seal_invalid", "The immutable persona label seal is invalid."
        ) from exc
    _validate_seal_ancestors(store, study_id, receipt)
    expected = canonical_sha256([item.model_dump(mode="json") for item in labels])
    if receipt.label_set_sha256 != expected:
        raise DataValidationError(
            "persona_label_seal_label_mismatch",
            "The final receipt does not bind the immutable sealed labels.",
        )
    return SealedPersonaLabels(receipt, labels, index)


def _validate_seal_ancestors(
    store: PersonaStudyStore, study_id: str, receipt: PersonaLabelSealReceipt
) -> None:
    initial = _initial_receipt(store, study_id)
    completed = initial_labels(store, study_id)
    if (
        receipt.initial_submission_receipt_sha256 != initial.receipt_sha256
        or initial.label_set_sha256 != canonical_sha256(completed.model_dump(mode="json"))
    ):
        raise DataValidationError(
            "persona_label_seal_ancestor_mismatch",
            "The final seal does not bind its immutable initial submission.",
        )
    if receipt.adjudication_set_sha256 is None:
        return
    adjudication = _sealed_adjudication(store, study_id)
    if (
        adjudication.initial_receipt_sha256 != initial.receipt_sha256
        or canonical_sha256(adjudication.model_dump(mode="json")) != receipt.adjudication_set_sha256
    ):
        raise DataValidationError(
            "persona_label_seal_ancestor_mismatch",
            "The final seal does not bind its immutable adjudication set.",
        )


def _sealed_adjudication(store: PersonaStudyStore, study_id: str) -> CompletedRepeatAdjudicationSet:
    try:
        return CompletedRepeatAdjudicationSet.model_validate_json(
            store.read_artifact(study_id, ADJUDICATION_PATH)
        )
    except ValidationError as exc:
        raise DataValidationError(
            "persona_label_adjudication_invalid",
            "The immutable repeat adjudication is invalid.",
        ) from exc
