from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.errors import DataValidationError
from ynoy.models import CompletedRepeatAdjudicationSet
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.label_contract import (
    ADJUDICATION_PATH,
    INITIAL_LABELS_PATH,
    INITIAL_RECEIPT_PATH,
)
from ynoy.persona_study.label_submission import PersonaLabelSubmission, submit_persona_labels
from ynoy.persona_study.labels import seal_persona_labels
from ynoy.persona_study.prepare import PreparedPersonaStudy, prepare_persona_study
from ynoy.util import canonical_sha256

_NOW = datetime(2026, 2, 1, tzinfo=UTC)
_LEGACY_LABEL_INSTRUCTIONS = (
    "Her null alani yalniz kendi yarginla doldur.",
    "Yapisal user rolu, sozlerin sana ait oldugunu kanitlamaz.",
    "Kart tanidik gelse bile onceki yaniti kopyalama.",
    "Exact span alanlarinda focus metnindeki karakter araliklarini kullan.",
    "Ilk submit-labels islemi cevaplarini immutable yapar; once yerel kopyani kontrol et.",
    "Blind-repeat uyusmazligi olursa ilk cevaplar korunur ve ayri adjudication acilir.",
    "Bitirdiginde completed_by alanini represented_user yap.",
)
_LEGACY_ADJUDICATION_INSTRUCTIONS = (
    "Bu dosya ilk submission'i degistirmez; yalniz uyusmayan tekrar ciftlerini karara baglar.",
    "initial_judgments alanlarini degistirme.",
    "Her final_judgment ve adjudication_reason alanini kendi yarginla doldur.",
    "Bitirdiginde completed_by alanini represented_user yap.",
)


def _study(tmp_path: Path) -> tuple[PersonaStudyStore, PreparedPersonaStudy]:
    source, _ = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    result = prepare_persona_study(source, private, synthetic=True, evaluation_time=_NOW)
    return PersonaStudyStore(private, real_data=False, evaluation_time=_NOW), result


def _complete_draft(result: PreparedPersonaStudy) -> dict[str, object]:
    template = json.loads(result.labels_path.read_text(encoding="utf-8"))
    presentations_path = result.review_path.parent / "presentations.json"
    presentations = json.loads(presentations_path.read_text(encoding="utf-8"))
    focus = {item["presentation_id"]: item["focus"]["content"] for item in presentations}
    template["completed_by"] = "represented_user"
    for label in template["labels"]:
        text = focus[label["presentation_id"]]
        label.update(
            {
                "authorship": "self",
                "claim_holder": "self",
                "adoption": "endorsed",
                "decision": "accept",
                "target_layer": "persona",
                "persona_kind": "preference",
                "scope": {
                    "project": None,
                    "role": None,
                    "audience": None,
                    "risk": "low",
                    "temporal": None,
                },
                "rationale_spans": [{"start": 0, "end": 1, "text": text[:1]}],
                "evidence_demand_spans": [],
                "should_abstain": False,
                "exclude_from_persona": False,
                "exclusion_reason": None,
                "confidence": "high",
                "notes": None,
            }
        )
    return template


def _write_draft(result: PreparedPersonaStudy, value: dict[str, object]) -> None:
    result.labels_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _blind_map(store: PersonaStudyStore, study_id: str) -> list[dict[str, object]]:
    return json.loads(store.read_artifact(study_id, "evaluator/blind-map.json"))


def _mismatch_submission(
    tmp_path: Path,
) -> tuple[PersonaStudyStore, PreparedPersonaStudy, PersonaLabelSubmission]:
    store, result = _study(tmp_path)
    draft = _complete_draft(result)
    repeated = next(
        item for item in _blind_map(store, result.manifest.study_id) if item["repeated"]
    )
    labels = {item["presentation_id"]: item for item in draft["labels"]}
    labels[repeated["presentation_id"]]["decision"] = "reject"
    _write_draft(result, draft)
    return store, result, submit_persona_labels(store, result.manifest.study_id)


def _complete_adjudication(
    store: PersonaStudyStore,
    study_id: str,
    template: bytes,
    *,
    tamper_initial: bool,
) -> None:
    path = store.paths.artifact(study_id, ADJUDICATION_PATH)
    value = json.loads(template)
    value["completed_by"] = "represented_user"
    for item in value["adjudications"]:
        item["final_judgment"] = json.loads(json.dumps(item["initial_judgments"][0]))
        item["adjudication_reason"] = "Synthetic represented-user resolution."
    if tamper_initial:
        value["adjudications"][0]["initial_judgments"][0]["decision"] = "correct"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_completed_repeats_seal_to_24_non_promoted_labels(tmp_path: Path) -> None:
    store, result = _study(tmp_path)
    _write_draft(result, _complete_draft(result))

    submitted = submit_persona_labels(store, result.manifest.study_id)
    sealed = seal_persona_labels(store, result.manifest.study_id)
    replay = seal_persona_labels(store, result.manifest.study_id)

    assert submitted.initial_receipt.repeat_exact_match_count == 8
    assert submitted.initial_receipt.adjudication_required is False
    assert submitted.seal_receipt == sealed.receipt
    assert replay.receipt == sealed.receipt and replay.labels == sealed.labels
    assert len(sealed.labels) == 24
    assert sealed.receipt.repeat_pair_count == 8
    assert sealed.receipt.initial_repeat_exact_match_count == 8
    assert sealed.receipt.adjudicated_repeat_pair_count == 0
    assert sealed.receipt.adjudication_set_sha256 is None
    assert sealed.receipt.persona_candidate_count == 24
    assert sealed.receipt.persona_quality_claimed is False
    assert sealed.receipt.protected_holdout_used is False
    assert sealed.receipt.interpretation_authority == "represented_user_local_attestation"
    assert sealed.receipt.identity_authentication == "local_operator_attestation_not_cryptographic"
    assert all(
        not item.core_eligible and not item.automatic_core_promotion for item in sealed.labels
    )
    assert all(
        item.identity_authentication == "local_operator_attestation_not_cryptographic"
        for item in sealed.labels
    )
    entries = {item.relative_path: item for item in sealed.artifact_index.entries}
    assert entries["annotator/labels.template.json"].mutable_by == "none"
    assert "evaluator/labels.sealed.json" in entries
    assert "evaluator/label-seal.json" in entries
    assert ADJUDICATION_PATH not in entries


def test_incomplete_template_fails_without_sealing(tmp_path: Path) -> None:
    store, result = _study(tmp_path)

    with pytest.raises(DataValidationError) as error:
        submit_persona_labels(store, result.manifest.study_id)

    assert error.value.code == "persona_labels_incomplete_or_invalid"
    index = store.read_index(result.manifest.study_id)
    draft = next(
        item for item in index.entries if item.relative_path.endswith("labels.template.json")
    )
    assert draft.mutable_by == "represented_user"


def test_mismatch_submission_is_immutable_and_requires_safe_adjudication(tmp_path: Path) -> None:
    store, result, submitted = _mismatch_submission(tmp_path)
    study_id = result.manifest.study_id
    initial_labels = store.read_artifact(study_id, INITIAL_LABELS_PATH)
    initial_receipt = store.read_artifact(study_id, INITIAL_RECEIPT_PATH)
    adjudication_template = store.read_artifact(study_id, ADJUDICATION_PATH, allow_user_draft=True)
    mismatch = next(item for item in submitted.initial_receipt.pair_results if not item.exact_match)

    assert submitted.initial_receipt.repeat_mismatch_count == 1
    assert submitted.initial_receipt.adjudication_required is True
    assert len(json.loads(initial_labels)["labels"]) == 32
    assert len(submitted.initial_receipt.pair_results) == 8
    assert "decision" in mismatch.mismatching_fields
    assert submitted.sealed_labels == () and submitted.seal_receipt is None
    with pytest.raises(DataValidationError) as incomplete:
        seal_persona_labels(store, study_id)
    assert incomplete.value.code == "persona_label_adjudication_incomplete"

    _complete_adjudication(store, study_id, adjudication_template, tamper_initial=True)
    with pytest.raises(DataValidationError) as tampered:
        seal_persona_labels(store, study_id)
    assert tampered.value.code == "persona_label_adjudication_initial_changed"

    _complete_adjudication(store, study_id, adjudication_template, tamper_initial=False)
    sealed = seal_persona_labels(store, study_id)
    replay = seal_persona_labels(store, study_id)
    immutable_adjudication = CompletedRepeatAdjudicationSet.model_validate_json(
        store.read_artifact(study_id, ADJUDICATION_PATH)
    )
    assert sealed.receipt.adjudicated_repeat_pair_count == 1
    assert sealed.receipt.initial_repeat_exact_match_count == 7
    assert sealed.receipt.adjudication_set_sha256 == canonical_sha256(
        immutable_adjudication.model_dump(mode="json")
    )
    assert replay.receipt == sealed.receipt and replay.labels == sealed.labels
    assert store.read_artifact(study_id, INITIAL_LABELS_PATH) == initial_labels
    assert store.read_artifact(study_id, INITIAL_RECEIPT_PATH) == initial_receipt


def test_non_exact_span_fails_closed(tmp_path: Path) -> None:
    store, result = _study(tmp_path)
    draft = _complete_draft(result)
    first = draft["labels"][0]
    original = first["rationale_spans"][0]["text"]
    first["rationale_spans"][0]["text"] = "x" if original != "x" else "y"
    _write_draft(result, draft)

    with pytest.raises(DataValidationError) as error:
        submit_persona_labels(store, result.manifest.study_id)

    assert error.value.code == "persona_label_span_mismatch"


def test_non_self_text_cannot_enter_persona(tmp_path: Path) -> None:
    store, result = _study(tmp_path)
    draft = _complete_draft(result)
    draft["labels"][0]["authorship"] = "quoted_or_pasted"
    _write_draft(result, draft)

    with pytest.raises(DataValidationError) as error:
        submit_persona_labels(store, result.manifest.study_id)

    assert error.value.code == "persona_labels_incomplete_or_invalid"


def test_legacy_label_contract_can_be_submitted_without_rewriting_history(tmp_path: Path) -> None:
    store, result = _study(tmp_path)
    draft = _complete_draft(result)
    draft["schema_version"] = "persona-labels/0.1"
    draft["instructions"] = list(_LEGACY_LABEL_INSTRUCTIONS)
    _write_draft(result, draft)

    submitted = submit_persona_labels(store, result.manifest.study_id)

    assert submitted.initial_receipt.repeat_exact_match_count == 8
    assert submitted.seal_receipt is not None


def test_legacy_adjudication_contract_can_be_sealed_without_rewriting_history(
    tmp_path: Path,
) -> None:
    store, result, submitted = _mismatch_submission(tmp_path)
    study_id = result.manifest.study_id
    template = json.loads(store.read_artifact(study_id, ADJUDICATION_PATH, allow_user_draft=True))
    template["schema_version"] = "persona-repeat-adjudication/0.1"
    template["instructions"] = list(_LEGACY_ADJUDICATION_INSTRUCTIONS)
    _complete_adjudication(
        store,
        study_id,
        json.dumps(template, ensure_ascii=False).encode(),
        tamper_initial=False,
    )

    sealed = seal_persona_labels(store, study_id)

    assert submitted.initial_receipt.adjudication_required is True
    assert sealed.receipt.adjudicated_repeat_pair_count == 1
