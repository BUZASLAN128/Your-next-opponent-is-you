from __future__ import annotations

from ynoy.models import (
    AnnotationPresentation,
    BlindMapEntry,
    PersonaAnnotationJudgment,
    PersonaModelProposal,
)
from ynoy.persona_study.label_contract import repeat_groups
from ynoy.util import sha256_text

BASE_AUDIT_COUNT = 8


def base_audit_ids(study_id: str, cards: tuple[AnnotationPresentation, ...]) -> set[str]:
    longest = sorted(cards, key=lambda item: (-len(item.focus.content), item.presentation_id))[:2]
    selected = {item.presentation_id for item in longest}
    ranked = sorted(cards, key=lambda item: sha256_text(f"{study_id}:audit:{item.presentation_id}"))
    for item in ranked:
        if len(selected) == BASE_AUDIT_COUNT:
            break
        selected.add(item.presentation_id)
    return selected


def oversized_guard(focus: str) -> PersonaAnnotationJudgment:
    return PersonaAnnotationJudgment.model_validate(
        {
            "authorship": "unknown",
            "claim_holder": "unknown",
            "adoption": "unknown",
            "decision": "unknown",
            "target_layer": "unknown",
            "persona_kind": None,
            "scope": {"risk": "unknown"},
            "rationale_spans": [{"start": 0, "end": len(focus), "text": focus}],
            "evidence_demand_spans": [],
            "should_abstain": True,
            "exclude_from_persona": True,
            "exclusion_reason": "uncertain",
            "confidence": "unknown",
            "notes": None,
        }
    )


def repeat_review_ids(
    cards: tuple[AnnotationPresentation, ...],
    mapping: tuple[BlindMapEntry, ...],
    proposals: tuple[PersonaModelProposal, ...],
) -> tuple[set[str], int]:
    groups = repeat_groups(cards, mapping)
    by_id = {item.presentation_id: item for item in proposals}
    review: set[str] = set()
    disagreements = 0
    for entries in groups.values():
        if len(entries) != 2:
            continue
        pair = tuple(by_id[item.presentation_id] for item in entries)
        judgments = tuple(item.chosen_judgment for item in pair)
        if None in judgments or judgments[0] != judgments[1]:
            disagreements += 1
            review.update(item.presentation_id for item in entries)
    return review, disagreements
