from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from support.persona_assisted import NOW, FakeProposer, judgment, outside_audit, prepared_study
from ynoy.models import AnnotationPresentation, DataClass, PersonaAnnotationJudgment
from ynoy.persona_study.artifact_contract import artifact_index
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.assisted_attempts import PROPOSALS_PATH, RETRY_PROPOSALS_PATH
from ynoy.persona_study.assisted_labels import propose_assisted_labels
from ynoy.persona_study.assisted_review import QUICK_REVIEW_PATH, RETRY_QUICK_REVIEW_PATH
from ynoy.persona_study.label_contract import presentations
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes


@dataclass(frozen=True, slots=True)
class ActiveReviewStudy:
    store: PersonaStudyStore
    study_id: str
    draft_path: str
    cards: tuple[AnnotationPresentation, ...]

    def draft(self) -> dict[str, object]:
        raw = self.store.read_artifact(self.study_id, self.draft_path, allow_user_draft=True)
        return json.loads(raw)

    def selected_orders(self) -> tuple[int, ...]:
        return tuple(item["order"] for item in self.draft()["actions"])

    def focus(self, order: int) -> str:
        return next(item.focus.content for item in self.cards if item.order == order)


def active_review_study(
    tmp_path: Path,
    *,
    retry: bool = False,
    unconfirmable: bool = False,
    real_shaped: bool = False,
    evaluation_time: datetime = NOW,
) -> ActiveReviewStudy:
    store, prepared = prepared_study(tmp_path, evaluation_time=evaluation_time)
    study_id = prepared.manifest.study_id
    if real_shaped:
        store.append_artifacts(
            study_id,
            (
                ArtifactPayload(
                    "evaluator/synthetic-d2-sentinel.json",
                    b"{}",
                    DataClass.DERIVED_IDENTITY,
                    (canonical_sha256((study_id, "synthetic-d2")),),
                ),
            ),
        )
    if retry:
        _unreliable_primary(store, study_id)
        propose_assisted_labels(store, study_id, FakeProposer(), attempt="retry_01")
        draft_path = RETRY_QUICK_REVIEW_PATH
    else:
        proposer = FakeProposer()
        if unconfirmable:
            proposer.disagreement_orders.add(outside_audit(store, study_id, 1)[0])
        propose_assisted_labels(store, study_id, proposer)
        draft_path = QUICK_REVIEW_PATH
    return ActiveReviewStudy(store, study_id, draft_path, presentations(store, study_id))


def corrected_judgment(study: ActiveReviewStudy, order: int) -> PersonaAnnotationJudgment:
    return judgment(study.focus(order), persona=True)


def forge_selected_focus_mismatch(study: ActiveReviewStudy) -> None:
    proposal_path = RETRY_PROPOSALS_PATH if "retry-01" in study.draft_path else PROPOSALS_PATH
    index = study.store.read_index(study.study_id)
    bundle = json.loads(study.store.read_artifact(study.study_id, proposal_path))
    draft = study.draft()
    selected = next(item for item in bundle["proposals"] if item["selected_for_review"])
    selected["focus_sha256"] = "0" * 64
    receipt = bundle["receipt"]
    receipt["proposal_set_sha256"] = canonical_sha256(bundle["proposals"])
    receipt["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    draft["proposal_receipt_sha256"] = receipt["receipt_sha256"]
    bundle_bytes = canonical_json_bytes(bundle)
    study.store.paths.artifact(study.study_id, proposal_path).write_bytes(bundle_bytes)
    study.store.paths.artifact(study.study_id, study.draft_path).write_bytes(
        canonical_json_bytes(draft)
    )
    entries = tuple(
        item.model_copy(update={"sha256": sha256_bytes(bundle_bytes)})
        if item.relative_path == proposal_path
        else item
        for item in index.entries
    )
    study.store._write_index(
        artifact_index(study.study_id, index.created_at, index.expires_at, entries)
    )


def _unreliable_primary(store: PersonaStudyStore, study_id: str) -> None:
    proposer = FakeProposer()
    targets = outside_audit(store, study_id, 5)
    proposer.invalid.update(
        (order, pass_name) for order in targets for pass_name in ("direct", "skeptical")
    )
    result = propose_assisted_labels(store, study_id, proposer)
    assert result.bundle.receipt.status == "unreliable"
