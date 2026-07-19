from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ynoy.constants import PERSONA_STUDY_STABILITY_MINUTES
from ynoy.corpus.codex_discovery import (
    CodexDiscovery,
    DiscoveredCodexFile,
    discovery_key,
)
from ynoy.errors import DataValidationError
from ynoy.models import PersonaStudyManifest, ProtectedHoldoutFreeze
from ynoy.models.full_persona_exclusion import (
    FullCorpusExclusion,
    FullCorpusExclusionReason,
)


@dataclass(frozen=True, slots=True)
class ExcludedSource:
    item: DiscoveredCodexFile
    reason: FullCorpusExclusionReason


def stability_cutoff_ns(study: PersonaStudyManifest, freeze: ProtectedHoldoutFreeze) -> int:
    contract_time = min(study.created_at, freeze.created_at)
    stable = contract_time - timedelta(minutes=PERSONA_STUDY_STABILITY_MINUTES)
    return min(int(stable.timestamp() * 1_000_000_000), freeze.boundary_session_start_ns - 1)


def partition_sources(
    files: tuple[DiscoveredCodexFile, ...], stable_before_ns: int
) -> tuple[tuple[DiscoveredCodexFile, ...], tuple[ExcludedSource, ...]]:
    included: list[DiscoveredCodexFile] = []
    excluded: list[ExcludedSource] = []
    for item in files:
        if item.modified_ns > stable_before_ns:
            excluded.append(ExcludedSource(item, "modified_after_stability_cutoff"))
        elif item.file_bytes == 0:
            excluded.append(ExcludedSource(item, "empty_at_freeze"))
        else:
            included.append(item)
    return tuple(included), tuple(excluded)


def verify_discovery_replay(
    before: CodexDiscovery, after: CodexDiscovery, stable_before_ns: int
) -> None:
    first_sources, first_excluded = partition_sources(before.files, stable_before_ns)
    next_sources, next_excluded = partition_sources(after.files, stable_before_ns)
    first_key = discovery_key(CodexDiscovery(first_sources, before.ignored_noncanonical_files))
    next_key = discovery_key(CodexDiscovery(next_sources, after.ignored_noncanonical_files))
    if first_key != next_key or exclusion_key(first_excluded) != exclusion_key(next_excluded):
        raise DataValidationError(
            "full_persona_source_universe_changed",
            "The canonical source universe changed while it was frozen.",
        )


def exclusion_key(values: tuple[ExcludedSource, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (value.item.partition, value.item.relative.as_posix(), value.reason) for value in values
    )


def manifest_exclusion_key(
    values: tuple[FullCorpusExclusion, ...],
) -> tuple[tuple[str, str, str], ...]:
    return tuple((value.partition, value.relative_locator, value.reason) for value in values)
