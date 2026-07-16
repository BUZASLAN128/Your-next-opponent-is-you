from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from ynoy.models import (
    BlindMapEntry,
    CompletedPersonaLabelSet,
    DataClass,
    PersonaAnnotationLabel,
    PersonaInitialLabelReceipt,
    PersonaLabelSealReceipt,
    RepeatPairAgreement,
    SealedPersonaLabel,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.label_contract import (
    ADJUDICATION_PATH,
    AGREEMENT_FIELDS,
    INITIAL_LABELS_PATH,
    INITIAL_RECEIPT_PATH,
    LABEL_PATH,
    SEAL_RECEIPT_PATH,
    SEALED_LABELS_PATH,
    blind_map,
    completed_labels_with_digest,
    dependencies,
    derived_class,
    final_receipt,
    judgment,
    presentations,
    repeat_groups,
    sealed_label,
    validate_completed_labels,
)
from ynoy.util import canonical_json_bytes, canonical_sha256

ADJUDICATION_INSTRUCTIONS = (
    "Bu dosya ilk submission'i degistirmez; yalniz uyusmayan tekrar ciftlerini karara baglar.",
    "initial_judgments alanlarini degistirme.",
    "Her final_judgment ve adjudication_reason alanini kendi yarginla doldur.",
    "Bitirdiginde completed_by alanini represented_user yap.",
)


@dataclass(frozen=True, slots=True)
class PersonaLabelSubmission:
    initial_receipt: PersonaInitialLabelReceipt
    artifact_index: StudyArtifactIndex
    sealed_labels: tuple[SealedPersonaLabel, ...] = ()
    seal_receipt: PersonaLabelSealReceipt | None = None


def submit_persona_labels(store: PersonaStudyStore, study_id: str) -> PersonaLabelSubmission:
    index = store.read_index(study_id)
    cards = presentations(store, study_id)
    mapping = blind_map(store, study_id)
    completed, draft_sha256 = completed_labels_with_digest(store, study_id)
    validate_completed_labels(completed, cards, mapping)
    groups = repeat_groups(cards, mapping)
    label_by_id = {item.presentation_id: item for item in completed.labels}
    receipt = _initial_receipt(completed, groups, label_by_id)
    data_class = derived_class(index)
    source_dependencies = dependencies(index)
    payloads = [
        ArtifactPayload(
            INITIAL_LABELS_PATH,
            canonical_json_bytes(completed.model_dump(mode="json")),
            data_class,
            source_dependencies,
        ),
        ArtifactPayload(
            INITIAL_RECEIPT_PATH,
            canonical_json_bytes(receipt.model_dump(mode="json")),
            data_class,
            source_dependencies,
        ),
    ]
    sealed: tuple[SealedPersonaLabel, ...] = ()
    final: PersonaLabelSealReceipt | None = None
    if receipt.adjudication_required:
        payloads.append(
            ArtifactPayload(
                ADJUDICATION_PATH,
                canonical_json_bytes(
                    _adjudication_template(completed, receipt, groups, label_by_id)
                ),
                data_class,
                source_dependencies,
                "represented_user",
            )
        )
    else:
        sealed = _initial_sealed(groups, label_by_id)
        final = final_receipt(completed, sealed, receipt, 0)
        payloads.extend(_final_payloads(sealed, final, data_class, source_dependencies))
    updated = store.seal_mutable_artifact(
        study_id,
        LABEL_PATH,
        tuple(payloads),
        expected_mutable_sha256=draft_sha256,
    )
    return PersonaLabelSubmission(receipt, updated, sealed, final)


def _initial_receipt(
    completed: CompletedPersonaLabelSet,
    groups: dict[str, tuple[BlindMapEntry, ...]],
    labels: dict[str, PersonaAnnotationLabel],
) -> PersonaInitialLabelReceipt:
    field_counts = {field: 0 for field in AGREEMENT_FIELDS}
    results: list[RepeatPairAgreement] = []
    for window_id, entries in sorted(groups.items()):
        if len(entries) != 2:
            continue
        first, second = (labels[item.presentation_id] for item in entries)
        matching = tuple(
            field for field in AGREEMENT_FIELDS if getattr(first, field) == getattr(second, field)
        )
        mismatching = tuple(field for field in AGREEMENT_FIELDS if field not in matching)
        for field in matching:
            field_counts[field] += 1
        results.append(
            RepeatPairAgreement(
                window_id=window_id,
                source_presentation_ids=cast(
                    tuple[str, str], tuple(item.presentation_id for item in entries)
                ),
                matching_fields=matching,
                mismatching_fields=mismatching,
                exact_match=not mismatching,
            )
        )
    exact = sum(item.exact_match for item in results)
    payload = {
        "study_id": completed.study_id,
        "label_set_sha256": canonical_sha256(completed.model_dump(mode="json")),
        "repeat_exact_match_count": exact,
        "repeat_mismatch_count": 8 - exact,
        "field_agreement_counts": field_counts,
        "pair_results": tuple(results),
        "adjudication_required": exact != 8,
    }
    draft = cast(Any, PersonaInitialLabelReceipt).model_construct(
        **payload, receipt_sha256="0" * 64
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"receipt_sha256"}))
    return PersonaInitialLabelReceipt.model_validate({**payload, "receipt_sha256": digest})


def _adjudication_template(
    completed: CompletedPersonaLabelSet,
    receipt: PersonaInitialLabelReceipt,
    groups: dict[str, tuple[BlindMapEntry, ...]],
    labels: dict[str, PersonaAnnotationLabel],
) -> dict[str, object]:
    mismatches = {item.window_id for item in receipt.pair_results if not item.exact_match}
    return {
        "schema_version": "persona-repeat-adjudication/0.1",
        "study_id": completed.study_id,
        "initial_receipt_sha256": receipt.receipt_sha256,
        "completed_by": None,
        "instructions": ADJUDICATION_INSTRUCTIONS,
        "adjudications": [
            {
                "window_id": window_id,
                "source_presentation_ids": [item.presentation_id for item in groups[window_id]],
                "initial_judgments": [
                    judgment(labels[item.presentation_id]).model_dump(mode="json")
                    for item in groups[window_id]
                ],
                "final_judgment": None,
                "adjudication_reason": None,
            }
            for window_id in sorted(mismatches)
        ],
    }


def _initial_sealed(
    groups: dict[str, tuple[BlindMapEntry, ...]], labels: dict[str, PersonaAnnotationLabel]
) -> tuple[SealedPersonaLabel, ...]:
    return tuple(
        sealed_label(window_id, entries, judgment(labels[entries[0].presentation_id]))
        for window_id, entries in sorted(groups.items())
    )


def _final_payloads(
    labels: tuple[SealedPersonaLabel, ...],
    receipt: PersonaLabelSealReceipt,
    data_class: DataClass,
    source_dependencies: tuple[str, ...],
) -> list[ArtifactPayload]:
    return [
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
    ]
