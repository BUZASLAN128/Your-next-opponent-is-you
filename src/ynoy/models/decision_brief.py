from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ynoy.models.base import DataClass, ScopeRef, StrictModel
from ynoy.models.review_vocab import (
    AtomicClaimType,
    ClaimModality,
    ReviewAction,
    ReviewOutcome,
    TargetLayer,
)

type Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

_CATEGORY_LAYERS: dict[str, frozenset[TargetLayer]] = {
    "protected_controls": frozenset({TargetLayer.PROTECTED_CONTROL}),
    "project_rules": frozenset({TargetLayer.PROJECT_CONSTITUTION, TargetLayer.SCOPED_POLICY}),
    "active_missions": frozenset({TargetLayer.MISSION_STATE}),
    "episodic_context": frozenset({TargetLayer.EPISODIC_MEMORY}),
    "persona_candidates": frozenset({TargetLayer.PERSONA_CANDIDATE}),
    "research_candidates": frozenset(
        {
            TargetLayer.ARCHITECTURE_CANDIDATE,
            TargetLayer.EXPERIMENT_BACKLOG,
            TargetLayer.RESEARCH_VISION,
        }
    ),
}
_ACTION_OUTCOMES = {
    ReviewAction.CONFIRM: ReviewOutcome.CONFIRMED,
    ReviewAction.REJECT: ReviewOutcome.REJECTED,
    ReviewAction.SPLIT: ReviewOutcome.SPLIT,
    ReviewAction.NARROW_SCOPE: ReviewOutcome.REVISED,
    ReviewAction.MARK_TEMPORARY: ReviewOutcome.REVISED,
    ReviewAction.MAKE_PROJECT_RULE: ReviewOutcome.REVISED,
    ReviewAction.REJECT_INFERENCE: ReviewOutcome.REVISED,
    ReviewAction.PROPOSE_FOR_CORE: ReviewOutcome.CORE_REVIEW_REQUESTED,
}


class DecisionBriefEntry(StrictModel):
    claim_id: UUID
    source_claim_id: UUID
    statement: str = Field(min_length=1)
    modality: ClaimModality
    claim_type: AtomicClaimType
    target_layer: TargetLayer
    scope: ScopeRef
    review_outcome: ReviewOutcome
    review_action: ReviewAction
    source_receipt_id: UUID
    correction_receipt_id: UUID
    correction_receipt_sha256: Sha256Digest
    core_eligible: Literal[False] = False

    @model_validator(mode="after")
    def action_and_outcome_are_consistent(self) -> DecisionBriefEntry:
        expected = _ACTION_OUTCOMES[self.review_action]
        if self.review_outcome != expected or expected == ReviewOutcome.REJECTED:
            raise ValueError("active decision entry contradicts its review action")
        return self


class DecisionConflict(StrictModel):
    target_layer: TargetLayer
    claim_ids: tuple[UUID, ...] = Field(min_length=2)
    reason: Literal["opposing_modalities_applicable_scope"] = "opposing_modalities_applicable_scope"

    @model_validator(mode="after")
    def claim_identifiers_are_unique(self) -> DecisionConflict:
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("decision conflict claim identifiers must be unique")
        return self


class DecisionBrief(StrictModel):
    """A scoped, non-reasoning view of reviewed decisions and unresolved state."""

    subject_id: str = Field(min_length=1)
    data_class: DataClass
    source_name: str = Field(min_length=1)
    source_conversation_id: str = Field(min_length=1)
    source_turn_id: str = Field(min_length=1)
    requested_scope: ScopeRef
    evaluated_at: datetime
    protected_controls: tuple[DecisionBriefEntry, ...]
    project_rules: tuple[DecisionBriefEntry, ...]
    active_missions: tuple[DecisionBriefEntry, ...]
    episodic_context: tuple[DecisionBriefEntry, ...]
    persona_candidates: tuple[DecisionBriefEntry, ...]
    research_candidates: tuple[DecisionBriefEntry, ...]
    conflicts: tuple[DecisionConflict, ...]
    pending_claim_ids: tuple[UUID, ...]
    unknowns: tuple[str, ...]
    abstention_reasons: tuple[str, ...]
    used_source_receipt_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1)
    used_correction_receipt_ids: tuple[UUID, ...]
    used_correction_receipt_hashes: tuple[Sha256Digest, ...]
    abstained: bool
    database_used: Literal[False] = False
    provider_used: Literal[False] = False
    persistence_status: Literal["not_persisted"] = "not_persisted"
    authority: Literal["none"] = "none"
    action_status: Literal["not_performed"] = "not_performed"
    automatic_core_promotion: Literal[False] = False

    @model_validator(mode="after")
    def brief_is_consistent(self) -> DecisionBrief:
        source_identifiers = (
            self.source_name,
            self.source_conversation_id,
            self.source_turn_id,
        )
        if any(value != value.strip() for value in source_identifiers):
            raise ValueError("decision brief source identifiers must be trimmed")
        if self.subject_id != self.subject_id.strip():
            raise ValueError("decision brief subject must be trimmed")
        if self.requested_scope.person_id != self.subject_id:
            raise ValueError("decision brief scope must match its subject")
        if self.evaluated_at.utcoffset() is None:
            raise ValueError("decision brief evaluation time must be timezone-aware")
        entries = self.all_entries()
        if len({item.claim_id for item in entries}) != len(entries):
            raise ValueError("decision brief entries must have unique claim identifiers")
        if any(item.scope.person_id != self.subject_id for item in entries):
            raise ValueError("decision brief entries must retain the represented subject")
        _validate_brief_receipts(self, entries)
        for category, allowed_layers in _CATEGORY_LAYERS.items():
            if any(item.target_layer not in allowed_layers for item in getattr(self, category)):
                raise ValueError(f"decision brief category {category} contains a foreign layer")
        if len(set(self.abstention_reasons)) != len(self.abstention_reasons):
            raise ValueError("decision brief abstention reasons must be unique")
        if len(set(self.pending_claim_ids)) != len(self.pending_claim_ids):
            raise ValueError("decision brief pending claim identifiers must be unique")
        if len(set(self.unknowns)) != len(self.unknowns):
            raise ValueError("decision brief unknowns must be unique")
        if self.abstained != bool(self.abstention_reasons):
            raise ValueError("decision brief abstention must reflect its reasons")
        if bool(self.conflicts) != ("unresolved_conflict" in self.abstention_reasons):
            raise ValueError("decision conflicts and abstention reasons must align")
        if (not entries) != ("no_applicable_reviewed_decisions" in self.abstention_reasons):
            raise ValueError("empty decision brief must expose its abstention reason")
        return self

    def all_entries(self) -> tuple[DecisionBriefEntry, ...]:
        return (
            self.protected_controls
            + self.project_rules
            + self.active_missions
            + self.episodic_context
            + self.persona_candidates
            + self.research_candidates
        )


def _validate_brief_receipts(
    brief: DecisionBrief,
    entries: tuple[DecisionBriefEntry, ...],
) -> None:
    if len(brief.used_correction_receipt_ids) != len(brief.used_correction_receipt_hashes):
        raise ValueError("used correction receipt identifiers and hashes must align")
    if len(set(brief.used_correction_receipt_ids)) != len(brief.used_correction_receipt_ids):
        raise ValueError("used correction receipt identifiers must be unique")
    if len(set(brief.used_correction_receipt_hashes)) != len(brief.used_correction_receipt_hashes):
        raise ValueError("used correction receipt hashes must be unique")
    receipt_pairs = set(
        zip(
            brief.used_correction_receipt_ids,
            brief.used_correction_receipt_hashes,
            strict=True,
        )
    )
    if any(
        item.source_receipt_id not in brief.used_source_receipt_ids
        or (item.correction_receipt_id, item.correction_receipt_sha256) not in receipt_pairs
        for item in entries
    ):
        raise ValueError("decision brief entries must reference the used receipt chain")
