from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ynoy.models import (
    BootstrapDeclaration,
    CandidateStatus,
    ClaimCandidate,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    Mode,
    OutputEnvelope,
    ScopeRef,
)
from ynoy.reasoner import (
    EvidenceItem,
    Reasoner,
    ReasonerRequest,
    ReasonerResponse,
    ensure_reasoner_data_boundary,
)
from ynoy.scope import scope_is_active, scope_matches
from ynoy.util import utc_now


class MemoryReader(Protocol):
    def list_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]: ...

    def list_claim_candidates(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[ClaimCandidate]: ...


@dataclass(frozen=True, slots=True)
class SelectedEvidence:
    items: tuple[EvidenceItem, ...]
    wrong_scope_count: int
    stale_count: int
    conflict_count: int = 0


RankedEvidence = tuple[int, datetime, EvidenceItem]


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[\w-]+", value.casefold()) if len(token) > 2}


def _decision_marker(value: str) -> DecisionLabel | None:
    match = re.search(
        r"\bdecision\s*:\s*(accept|reject|correct|defer|ask|unknown)\b", value.casefold()
    )
    return DecisionLabel(match.group(1)) if match else None


def _validity_is_active(
    valid_from: datetime | None, valid_until: datetime | None, now: datetime
) -> bool:
    return scope_is_active(
        ScopeRef(valid_from=valid_from, valid_until=valid_until),
        now,
    )


def select_evidence(
    memory: MemoryReader,
    *,
    task: str,
    scope: ScopeRef,
    subject_id: str = "self",
    limit: int = 12,
) -> SelectedEvidence:
    task_tokens = _tokens(task)
    now = utc_now()
    declarations, declaration_scope, declaration_stale = _rank_declarations(
        memory.list_bootstrap_declarations(subject_id=subject_id), task_tokens, scope, now
    )
    candidates, candidate_scope, candidate_stale = _rank_candidates(
        memory.list_claim_candidates(subject_id=subject_id), task_tokens, scope, now
    )
    ranked = [*declarations, *candidates]
    ranked.sort(key=lambda item: (-item[0], -item[1].timestamp(), item[2].receipt_id))
    relevant = [item for score, _, item in ranked if score > 0][:limit]
    return SelectedEvidence(
        items=tuple(relevant),
        wrong_scope_count=declaration_scope + candidate_scope,
        stale_count=declaration_stale + candidate_stale,
        conflict_count=_conflict_count(relevant),
    )


def _rank_declarations(
    declarations: list[BootstrapDeclaration],
    task_tokens: set[str],
    scope: ScopeRef,
    now: datetime,
) -> tuple[list[RankedEvidence], int, int]:
    ranked: list[RankedEvidence] = []
    wrong_scope = stale = 0
    for declaration in declarations:
        if not scope_matches(declaration.scope, scope):
            wrong_scope += 1
            continue
        if not scope_is_active(declaration.scope, now):
            stale += 1
            continue
        overlap = len(task_tokens & _tokens(declaration.statement))
        label_marker = (
            f" decision:{declaration.decision_label.value}" if declaration.decision_label else ""
        )
        ranked.append(
            (
                overlap,
                declaration.created_at,
                EvidenceItem(
                    receipt_id=str(declaration.record_id),
                    text=f"{declaration.statement}{label_marker}",
                    data_class=declaration.data_class,
                    source_kind="explicit_declaration",
                    decision_label=declaration.decision_label
                    or _decision_marker(declaration.statement),
                ),
            )
        )
    return ranked, wrong_scope, stale


def _rank_candidates(
    candidates: list[ClaimCandidate],
    task_tokens: set[str],
    scope: ScopeRef,
    now: datetime,
) -> tuple[list[RankedEvidence], int, int]:
    ranked: list[RankedEvidence] = []
    wrong_scope = stale = 0
    for candidate in candidates:
        if candidate.status != CandidateStatus.CONFIRMED:
            continue
        if candidate.claim_holder != ClaimHolder.REPRESENTED_USER:
            continue
        if not candidate.origin_cluster_ids:
            continue
        if not scope_matches(candidate.scope, scope):
            wrong_scope += 1
            continue
        if not scope_is_active(candidate.scope, now) or not _validity_is_active(
            candidate.valid_from, candidate.valid_until, now
        ):
            stale += 1
            continue
        overlap = len(task_tokens & _tokens(candidate.proposition))
        ranked.append(
            (
                overlap,
                candidate.created_at,
                EvidenceItem(
                    receipt_id=str(candidate.record_id),
                    text=candidate.proposition,
                    data_class=DataClass.DERIVED_IDENTITY,
                    source_kind=f"candidate:{candidate.status.value}",
                    decision_label=_decision_marker(candidate.proposition),
                ),
            )
        )
    return ranked, wrong_scope, stale


def cold_start_mirror() -> OutputEnvelope:
    return OutputEnvelope(
        mode=Mode.MIRROR,
        answer="I do not yet have enough personal evidence to predict your judgment.",
        confidence=0.0,
        unknowns=("represented_user_decision", "decision_rationale"),
        personal_fit="unknown",
        question="What single rule most often makes you reject a proposed coding change?",
    )


def _conflict_count(items: list[EvidenceItem]) -> int:
    labels = {item.decision_label for item in items if item.decision_label is not None}
    return max(0, len(labels) - 1)


def _conflict_abstention() -> OutputEnvelope:
    return OutputEnvelope(
        mode=Mode.MIRROR,
        answer="I cannot choose between conflicting active decisions without your clarification.",
        confidence=0.0,
        unknowns=("conflicting_active_decisions",),
        personal_fit="unknown",
        question="Which active decision should govern this task?",
    )


def _cold_start_response(selected: SelectedEvidence) -> OutputEnvelope:
    result = cold_start_mirror()
    unknowns = list(result.unknowns)
    if selected.wrong_scope_count:
        unknowns.append("available_evidence_belongs_to_another_scope")
    if selected.stale_count:
        unknowns.append("stale_evidence_was_excluded")
    return result.model_copy(update={"unknowns": tuple(unknowns)})


def _reasoned_mirror_response(
    response: ReasonerResponse, selected: SelectedEvidence
) -> OutputEnvelope:
    unknowns = list(response.unknowns)
    if selected.stale_count:
        unknowns.append("stale_evidence_was_excluded")
    return OutputEnvelope(
        mode=Mode.MIRROR,
        answer=response.answer,
        answer_kind="untrusted_reasoner_advisory",
        confidence=response.confidence,
        evidence_receipts=tuple(item.receipt_id for item in selected.items),
        unknowns=tuple(unknowns),
        personal_fit="known" if response.predicted_label != DecisionLabel.UNKNOWN else "partial",
        question=(
            None
            if response.predicted_label != DecisionLabel.UNKNOWN
            else "Which option would you choose here, and what evidence decides it?"
        ),
    )


def mirror_predict(
    memory: MemoryReader,
    *,
    task: str,
    scope: ScopeRef,
    reasoner: Reasoner,
    task_data_class: DataClass = DataClass.PRIVATE_TASK,
    subject_id: str = "self",
) -> OutputEnvelope:
    selected = select_evidence(memory, task=task, scope=scope, subject_id=subject_id)
    if selected.conflict_count:
        return _conflict_abstention()
    if not selected.items:
        return _cold_start_response(selected)
    ensure_reasoner_data_boundary(reasoner, selected.items, task_data_class)
    response = reasoner.complete(
        ReasonerRequest(
            mode=Mode.MIRROR,
            task=task,
            task_data_class=task_data_class,
            evidence=selected.items,
        )
    )
    return _reasoned_mirror_response(response, selected)


def advisor_suggest(
    memory: MemoryReader,
    *,
    task: str,
    scope: ScopeRef,
    reasoner: Reasoner | None = None,
    task_data_class: DataClass = DataClass.PRIVATE_TASK,
    subject_id: str = "self",
) -> OutputEnvelope:
    selected = select_evidence(memory, task=task, scope=scope, subject_id=subject_id)
    if not selected.items or reasoner is None:
        return OutputEnvelope(
            mode=Mode.ADVISOR,
            answer=(
                "Generic advice: define the expected behavior, choose the smallest reversible "
                "change, and verify it with a focused test before expanding scope."
            ),
            confidence=0.35,
            unknowns=("personal_fit",),
            personal_fit="unknown",
            question="Which trade-off matters most for this task?",
        )
    ensure_reasoner_data_boundary(reasoner, selected.items, task_data_class)
    response = reasoner.complete(
        ReasonerRequest(
            mode=Mode.ADVISOR,
            task=task,
            task_data_class=task_data_class,
            evidence=selected.items,
        )
    )
    return OutputEnvelope(
        mode=Mode.ADVISOR,
        answer=response.answer,
        answer_kind="untrusted_reasoner_advisory",
        confidence=response.confidence,
        evidence_receipts=tuple(item.receipt_id for item in selected.items),
        unknowns=response.unknowns,
        personal_fit="partial",
    )
