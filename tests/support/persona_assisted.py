from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from support.persona_study import synthetic_codex_study_root
from ynoy.errors import AdapterError
from ynoy.models import (
    AnnotationPresentation,
    ExactTextSpan,
    PersonaAnnotationJudgment,
    PresentationMessage,
    ReviewProviderEvidence,
    Speaker,
)
from ynoy.persona_study import assisted_labels as assisted_module
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_gates import base_audit_ids
from ynoy.persona_study.label_contract import blind_map, repeat_groups
from ynoy.persona_study.local_proposer import LocalPersonaProposer
from ynoy.persona_study.prepare import PreparedPersonaStudy, prepare_persona_study
from ynoy.util import canonical_sha256

NOW = datetime(2026, 2, 1, tzinfo=UTC)
MODEL_SHA = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
PRIVATE_SENTINEL = "SYNTHETIC_PRIVATE_MODEL_ERROR_SENTINEL"
CANDIDATE_FIELDS = (
    "authorship",
    "claim_holder",
    "adoption",
    "decision",
    "target_layer",
    "persona_kind",
    "confidence",
)


def presentation(text: str = "Keep the proposal bounded.") -> AnnotationPresentation:
    return AnnotationPresentation(
        presentation_id=canonical_sha256(("presentation", text)),
        order=1,
        context=(PresentationMessage(speaker=Speaker.ASSISTANT, content="Synthetic context."),),
        focus=PresentationMessage(speaker=Speaker.USER, content=text),
    )


def judgment(text: str, *, persona: bool = True) -> PersonaAnnotationJudgment:
    return PersonaAnnotationJudgment.model_validate(
        {
            "authorship": "self" if persona else "other",
            "claim_holder": "self" if persona else "third_party",
            "adoption": "endorsed" if persona else "not_applicable",
            "decision": "accept" if persona else "none",
            "target_layer": "persona" if persona else "none",
            "persona_kind": "preference" if persona else None,
            "scope": {
                "project": None,
                "role": None,
                "audience": None,
                "risk": "low",
                "temporal": None,
            },
            "rationale_spans": [{"start": 0, "end": len(text), "text": text}],
            "evidence_demand_spans": [],
            "should_abstain": False,
            "exclude_from_persona": not persona,
            "exclusion_reason": None if persona else "not_self",
            "confidence": "high",
            "notes": None,
        }
    )


def candidate(value: PersonaAnnotationJudgment) -> dict[str, object]:
    dumped = value.model_dump(mode="json")
    return {field: dumped[field] for field in CANDIDATE_FIELDS}


def response(value: PersonaAnnotationJudgment | dict[str, object]) -> dict[str, object]:
    raw = candidate(value) if isinstance(value, PersonaAnnotationJudgment) else value
    return {"choices": [{"message": {"content": json.dumps(raw)}}]}


def local_proposer(*, attested: bool = True) -> LocalPersonaProposer:
    return LocalPersonaProposer(
        endpoint="http://127.0.0.1:18100/v1/chat/completions",
        model="ynoy-extractor-qwen3-8b-q4km",
        revision="7c41481f57cb95916b40956ab2f0b139b296d974",
        artifact_sha256=MODEL_SHA,
        local_attested=attested,
    )


class FakeProposer:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []
        self.disagreement_orders: set[int] = set()
        self.invalid: set[tuple[int, str]] = set()
        self.oversized_orders: set[int] = set()
        self.bad_span: set[tuple[int, str]] = set()
        self.unexpected: set[tuple[int, str]] = set()
        self.audit_was_selected = True

    @property
    def provider_evidence(self) -> ReviewProviderEvidence:
        return ReviewProviderEvidence(
            model="synthetic-persona-proposer",
            revision="fixture-r1",
            artifact_sha256=MODEL_SHA,
        )

    def propose(self, card: AnnotationPresentation, *, pass_name: str) -> PersonaAnnotationJudgment:
        assert self.audit_was_selected
        key = (card.order, pass_name)
        self.calls.append(key)
        if key in self.unexpected:
            raise RuntimeError("unexpected proposer failure")
        if key in self.invalid:
            raise AdapterError("fixture_invalid", PRIVATE_SENTINEL)
        if card.order in self.oversized_orders:
            raise AdapterError("persona_proposer_input_too_large", PRIVATE_SENTINEL)
        value = judgment(
            card.focus.content,
            persona=not (card.order in self.disagreement_orders and pass_name == "skeptical"),
        )
        if key in self.bad_span:
            value = value.model_copy(
                update={"rationale_spans": (ExactTextSpan(start=0, end=1, text="!"),)}
            )
        return value


def prepared_study(
    tmp_path: Path, *, evaluation_time: datetime = NOW
) -> tuple[PersonaStudyStore, PreparedPersonaStudy]:
    source, _ = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    prepared = prepare_persona_study(
        source, private, synthetic=True, evaluation_time=evaluation_time
    )
    store = PersonaStudyStore(private, real_data=False, evaluation_time=evaluation_time)
    return store, prepared


def base_audit_orders(store: PersonaStudyStore, study_id: str) -> set[int]:
    cards = assisted_module.presentations(store, study_id)
    selected = base_audit_ids(study_id, cards)
    return {item.order for item in cards if item.presentation_id in selected}


def outside_audit(store: PersonaStudyStore, study_id: str, count: int) -> tuple[int, ...]:
    base = base_audit_orders(store, study_id)
    cards = assisted_module.presentations(store, study_id)
    groups = repeat_groups(cards, blind_map(store, study_id))
    singles = {entries[0].presentation_id for entries in groups.values() if len(entries) == 1}
    return tuple(
        card.order for card in cards if card.presentation_id in singles and card.order not in base
    )[:count]


def repeat_pair_orders(store: PersonaStudyStore, study_id: str) -> tuple[int, int]:
    cards = assisted_module.presentations(store, study_id)
    order = {card.presentation_id: card.order for card in cards}
    groups = repeat_groups(cards, blind_map(store, study_id))
    pair = next(entries for entries in groups.values() if len(entries) == 2)
    return order[pair[0].presentation_id], order[pair[1].presentation_id]
