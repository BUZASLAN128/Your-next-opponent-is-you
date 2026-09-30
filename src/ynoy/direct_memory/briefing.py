from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from contextlib import closing
from datetime import datetime

from ynoy.decision_brief import resolve_decision_brief
from ynoy.direct_memory.claims import ClaimOperations
from ynoy.direct_memory.corrections import CorrectionOperations
from ynoy.direct_memory.database import DirectMemoryDatabase
from ynoy.direct_memory.models import DirectMemoryBrief, SourceEvent
from ynoy.direct_memory.reviews import ReviewOperations
from ynoy.direct_memory.source_events import SourceEventOperations
from ynoy.direct_memory.subject_scope import project_subject
from ynoy.errors import DataValidationError
from ynoy.models import ClaimModality
from ynoy.models.base import ScopeRef
from ynoy.models.decision_brief import DecisionBrief
from ynoy.review_replay import replay_interaction_review
from ynoy.util import canonical_sha256

_POSITIVE = {ClaimModality.MUST, ClaimModality.SHOULD, ClaimModality.PREFER}


class BriefOperations:
    def __init__(self, database: DirectMemoryDatabase, clock: Callable[[], datetime]) -> None:
        self.database = database
        self.sources = SourceEventOperations(database, clock)
        self.reviews = ReviewOperations(database, clock)
        self.corrections = CorrectionOperations(database, clock)
        self.claims = ClaimOperations(database, clock)

    def brief(self, project: str, *, as_of: datetime, known_at: datetime) -> DirectMemoryBrief:
        _validate_cutoffs(project, as_of, known_at)
        with closing(self.database.connect()) as connection:
            subject_id = project_subject(connection, project)
        source_events = self._visible_sources(project, as_of, known_at)
        claim_revisions = self.claims.list_claim_revisions(project, known_at=known_at, as_of=as_of)
        native_briefs, fact_keys = self._review_briefs(project, as_of, known_at, subject_id)
        conflicts = _unresolved_conflicts(native_briefs, fact_keys)
        reasons = _abstention_reasons(native_briefs, conflicts)
        return DirectMemoryBrief(
            project=project,
            as_of=as_of,
            known_at=known_at,
            source_events=source_events,
            claim_revisions=claim_revisions,
            native_briefs=tuple(native_briefs),
            native_brief_hashes=tuple(
                canonical_sha256(item.model_dump(mode="json")) for item in native_briefs
            ),
            unresolved_conflicts=conflicts,
            abstained=bool(reasons),
            abstention_reasons=reasons,
        )

    def _visible_sources(
        self, project: str, as_of: datetime, known_at: datetime
    ) -> tuple[SourceEvent, ...]:
        with closing(self.database.connect()) as connection:
            rows = connection.execute(
                "SELECT source_id FROM source_events WHERE project=? ORDER BY revision", (project,)
            ).fetchall()
        visible = []
        for row in rows:
            event = self.sources.get_source_event(str(row["source_id"]))
            if event.recorded_at <= known_at and (event.said_at is None or event.said_at <= as_of):
                visible.append(event)
        return tuple(visible)

    def _review_briefs(
        self, project: str, as_of: datetime, known_at: datetime, subject_id: str | None
    ) -> tuple[list[DecisionBrief], dict[str, str]]:
        with closing(self.database.connect()) as connection:
            rows = connection.execute(
                "SELECT review_id,source_id,recorded_at FROM reviews "
                "WHERE project=? ORDER BY revision",
                (project,),
            ).fetchall()
        briefs = []
        fact_keys: dict[str, str] = {}
        for row in rows:
            if datetime.fromisoformat(row["recorded_at"]) > known_at:
                continue
            stored = self.reviews.get_review(str(row["review_id"]))
            if subject_id is not None and stored.review.subject_id != subject_id:
                raise DataValidationError(
                    "direct_memory_project_subject_mismatch",
                    "Stored review subject does not match its project's live subject.",
                )
            source = self.sources.get_source_event(str(row["source_id"]))
            event_times = (source.said_at, stored.review.source.event_time)
            if any(value is not None and value > as_of for value in event_times):
                continue
            corrections = self.corrections.list_corrections(stored.review_id)
            prefix = []
            for item in corrections:
                if item.recorded_at > known_at:
                    break
                prefix.append(item.correction)
            state = replay_interaction_review(stored.review, tuple(prefix))
            briefs.append(
                resolve_decision_brief(
                    state,
                    ScopeRef(person_id=stored.review.subject_id, project=project),
                    as_of,
                )
            )
            for fact in self.reviews.review_facts(stored.review_id):
                fact_keys[str(fact["claim_id"])] = str(fact["fact_key"])
        return briefs, fact_keys


def _validate_cutoffs(project: str, as_of: datetime, known_at: datetime) -> None:
    if not project or project != project.strip():
        raise DataValidationError(
            "direct_memory_project_invalid", "Project must be non-empty and trimmed."
        )
    if as_of.utcoffset() is None or known_at.utcoffset() is None:
        raise DataValidationError(
            "direct_memory_cutoff_invalid", "Temporal cutoffs must be timezone-aware."
        )


def _unresolved_conflicts(
    briefs: list[DecisionBrief], fact_keys: dict[str, str]
) -> tuple[tuple[str, ...], ...]:
    groups: dict[tuple[str, str, str], list[tuple[ClaimModality, str]]] = defaultdict(list)
    for brief in briefs:
        for entry in brief.all_entries():
            key = (
                brief.subject_id,
                entry.target_layer.value,
                " ".join(entry.statement.casefold().split()),
            )
            groups[key].append((entry.modality, fact_keys.get(str(entry.source_claim_id), "")))
    conflicts = []
    for entries in groups.values():
        modalities = {item[0] for item in entries}
        if ClaimModality.MUST_NOT not in modalities or not modalities.intersection(_POSITIVE):
            continue
        fact_group = tuple(sorted(item[1] for item in entries if item[1]))
        if fact_group:
            conflicts.append(fact_group)
    return tuple(sorted(conflicts))


def _abstention_reasons(
    briefs: list[DecisionBrief], conflicts: tuple[tuple[str, ...], ...]
) -> tuple[str, ...]:
    reasons = []
    if not any(brief.all_entries() for brief in briefs):
        reasons.append("no_applicable_reviewed_decisions")
    if conflicts:
        reasons.append("unresolved_conflict")
    return tuple(reasons)


__all__ = ["BriefOperations"]
