from __future__ import annotations

from ynoy.errors import DataValidationError
from ynoy.models.persona_action_pilot import (
    ActionPilotCase,
    ActionPilotHistory,
    ActionSignal,
)
from ynoy.models.persona_harvest import HarvestCandidate

SIGNAL_TIE_ORDER: tuple[ActionSignal, ...] = (
    "correction",
    "evidence_demand",
    "scope_change",
    "decision",
    "abstention",
    "outcome_feedback",
)


def validate_action_split(
    history: tuple[HarvestCandidate, ...], sealed: tuple[HarvestCandidate, ...]
) -> None:
    history_sources = {item.source_receipt for item in history}
    sealed_sources = {item.source_receipt for item in sealed}
    history_conversations = {item.conversation_key for item in history}
    sealed_conversations = {item.conversation_key for item in sealed}
    all_candidates = (*history, *sealed)
    times = tuple(item.event_time for item in all_candidates)
    unique_receipts = {item.candidate_sha256 for item in all_candidates}
    invalid = (
        len(set(times)) != len(times)
        or tuple(sorted(times)) != times
        or history[-1].event_time >= sealed[0].event_time
        or bool(history_sources & sealed_sources)
        or bool(history_conversations & sealed_conversations)
        or len(unique_receipts) != len(all_candidates)
    )
    if invalid:
        raise DataValidationError(
            "action_pilot_split_invalid",
            "The chronological pilot split has time, source, lineage, or duplicate overlap.",
        )


def action_history(item: HarvestCandidate) -> ActionPilotHistory:
    return ActionPilotHistory(
        case_id=item.candidate_id,
        event_time=item.event_time,
        source_receipt=item.source_receipt,
        conversation_key=item.conversation_key,
        context=item.context,
        focus=item.focus,
        primary_signal=primary_signal(item),
    )


def action_case(item: HarvestCandidate) -> ActionPilotCase:
    return ActionPilotCase(
        case_id=item.candidate_id,
        event_time=item.event_time,
        source_receipt=item.source_receipt,
        conversation_key=item.conversation_key,
        context=item.context,
    )


def primary_signal(item: HarvestCandidate) -> ActionSignal:
    return next(signal for signal in SIGNAL_TIE_ORDER if signal in item.signal_tags)
