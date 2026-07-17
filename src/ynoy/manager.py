from __future__ import annotations

from datetime import datetime

from ynoy.core import advisor_suggest
from ynoy.models import (
    BootstrapDeclaration,
    CanonicalClaim,
    ManagerStartResult,
    OperatingMemorySeed,
    OperatingRule,
    ScopeRef,
)
from ynoy.task_input import validate_task


class _EmptyPersonaMemory:
    def list_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]:
        del subject_id, include_inactive
        return []

    def list_active_canonical_claims(
        self, *, subject_id: str = "self", evaluation_time: datetime
    ) -> list[CanonicalClaim]:
        del subject_id, evaluation_time
        return []


def build_operating_memory_seed() -> OperatingMemorySeed:
    """Build non-personal working rules that never enter persona retrieval."""
    rules = (
        OperatingRule(
            rule_id="evidence_honesty",
            instruction="Separate observed facts, explicit user statements, and hypotheses.",
        ),
        OperatingRule(
            rule_id="bounded_learning",
            instruction="Ask one bounded question when personal evidence is missing.",
        ),
        OperatingRule(
            rule_id="reversible_progress",
            instruction="Propose the smallest reversible step and require focused verification.",
        ),
        OperatingRule(
            rule_id="no_false_action",
            instruction="Never claim that an external action or memory promotion occurred.",
        ),
    )
    return OperatingMemorySeed(rules=rules)


def start_manager(*, task: str, scope: ScopeRef) -> ManagerStartResult:
    """Start a useful zero-persona session without storage or a model provider."""
    advisory = advisor_suggest(
        _EmptyPersonaMemory(),
        task=validate_task(task),
        scope=scope,
        reasoner=None,
    )
    return ManagerStartResult(
        operating_memory=build_operating_memory_seed(),
        advisory=advisory,
    )
