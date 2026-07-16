from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.models import BenchmarkCase, BenchmarkManifest, EvidenceRegime, Prediction
from ynoy.util import canonical_sha256

ALGORITHMS = (
    "no_personalization",
    "recent_context",
    "declared_profile",
    "static_summary",
    "lexical_retrieval",
    "frequency_profile",
    "structured_core",
)
REGIMES = tuple(EvidenceRegime)
PROTOCOL_VERSION = "temporal-mirror-pilot/1.0"
FATAL_GATES = (
    "fake_source_receipt",
    "assistant_text_laundered_as_user",
    "wrong_person_or_scope",
    "stale_rule_hidden",
    "persona_egress",
    "authority_escalation",
)


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    source = path.expanduser().resolve(strict=True)
    try:
        raw: Any = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "benchmark_cases_unreadable", "Benchmark cases must be valid UTF-8 JSON."
        ) from exc
    if not isinstance(raw, list):
        raise DataValidationError(
            "benchmark_cases_array_required", "Benchmark cases JSON must be an array."
        )
    try:
        cases = [BenchmarkCase.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise DataValidationError(
            "benchmark_case_invalid", "At least one benchmark case violates the frozen schema."
        ) from exc
    _validate_case_set(cases)
    return sorted(cases, key=lambda case: (case.event_time, case.case_id))


def _validate_case_set(cases: Sequence[BenchmarkCase]) -> None:
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise DataValidationError(
            "benchmark_case_id_duplicate", "Benchmark case IDs must be unique."
        )
    if len({case.dependency_cluster_id for case in cases}) < 2:
        raise DataValidationError(
            "benchmark_clusters_insufficient",
            "At least two dependency clusters are required for temporal holdout.",
        )


def split_dependency_clusters(
    cases: Sequence[BenchmarkCase], *, development_fraction: float
) -> tuple[list[BenchmarkCase], list[BenchmarkCase], datetime]:
    by_cluster: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        by_cluster[case.dependency_cluster_id].append(case)
    ordered = sorted(
        by_cluster,
        key=lambda cluster: (max(item.event_time for item in by_cluster[cluster]), cluster),
    )
    index = math.floor(len(ordered) * development_fraction)
    development_clusters = set(ordered[: max(1, min(len(ordered) - 1, index))])
    development = [case for case in cases if case.dependency_cluster_id in development_clusters]
    sealed = [case for case in cases if case.dependency_cluster_id not in development_clusters]
    if {item.dependency_cluster_id for item in development} & {
        item.dependency_cluster_id for item in sealed
    }:
        raise DataValidationError(
            "benchmark_dependency_leakage", "A dependency cluster crossed the temporal split."
        )
    if max(item.event_time for item in development) >= min(item.event_time for item in sealed):
        raise DataValidationError(
            "benchmark_temporal_leakage",
            "Every development event must precede every sealed event.",
        )
    return development, sealed, max(case.event_time for case in development)


def freeze_benchmark(
    name: str,
    cases: Sequence[BenchmarkCase],
    *,
    development_fraction: float = 0.7,
) -> BenchmarkManifest:
    if not 0.5 <= development_fraction <= 0.9:
        raise DataValidationError(
            "benchmark_split_invalid", "Development fraction must be between 0.5 and 0.9."
        )
    if not cases:
        raise DataValidationError("benchmark_empty", "Cannot freeze an empty benchmark.")
    development, sealed, cutoff = split_dependency_clusters(
        cases, development_fraction=development_fraction
    )
    case_digest = canonical_sha256([case.model_dump(mode="json") for case in cases])
    draft = BenchmarkManifest(
        name=name,
        case_ids=tuple(case.case_id for case in cases),
        development_case_ids=tuple(case.case_id for case in development),
        sealed_case_ids=tuple(case.case_id for case in sealed),
        dependency_clusters=tuple(sorted({case.dependency_cluster_id for case in cases})),
        development_fraction=development_fraction,
        temporal_cutoff=cutoff,
        case_set_sha256=case_digest,
        protocol_sha256=canonical_sha256(_protocol(development_fraction)),
        algorithms=ALGORITHMS,
        regimes=REGIMES,
    )
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"manifest_sha256"}))
    return draft.model_copy(update={"manifest_sha256": digest})


def _protocol(development_fraction: float) -> dict[str, object]:
    return {
        "version": PROTOCOL_VERSION,
        "split": "dependency-clustered temporal holdout",
        "development_fraction": development_fraction,
        "algorithms": ALGORITHMS,
        "regimes": [regime.value for regime in REGIMES],
        "fatal_gates": FATAL_GATES,
        "thresholds": "must be calibrated before a real sealed run",
        "target_visibility": "hidden from predictor functions",
    }


def verify_benchmark_manifest(manifest: BenchmarkManifest, cases: Sequence[BenchmarkCase]) -> None:
    expected_manifest = canonical_sha256(
        manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    )
    expected_cases = canonical_sha256([case.model_dump(mode="json") for case in cases])
    if expected_manifest != manifest.manifest_sha256:
        raise DataValidationError(
            "benchmark_manifest_digest_mismatch", "Benchmark manifest integrity check failed."
        )
    if expected_cases != manifest.case_set_sha256:
        raise DataValidationError(
            "benchmark_case_set_changed", "Benchmark cases changed after the manifest was frozen."
        )
    if tuple(case.case_id for case in cases) != manifest.case_ids:
        raise DataValidationError(
            "benchmark_case_order_changed", "Benchmark case order changed after freezing."
        )
    if manifest.algorithms != ALGORITHMS or manifest.regimes != REGIMES:
        raise DataValidationError(
            "benchmark_protocol_semantics_changed",
            "Frozen benchmark algorithms and regimes must match the protocol.",
        )
    if manifest.protocol_sha256 != canonical_sha256(_protocol(manifest.development_fraction)):
        raise DataValidationError(
            "benchmark_protocol_digest_mismatch",
            "Frozen benchmark protocol does not match the implementation protocol.",
        )
    _assert_partition_complete(manifest, cases)
    _assert_clusters_separate(manifest, cases)
    _assert_temporal_cutoff(manifest, cases)


def evaluate_fatal_gates(
    case: BenchmarkCase, prediction: Prediction | None = None
) -> tuple[str, ...]:
    """Return explicit protocol violations marked on a synthetic challenge case."""
    del prediction
    return tuple(sorted(set(case.challenge_tags) & set(FATAL_GATES)))


def _assert_partition_complete(manifest: BenchmarkManifest, cases: Sequence[BenchmarkCase]) -> None:
    case_ids = tuple(case.case_id for case in cases)
    development = manifest.development_case_ids
    sealed = manifest.sealed_case_ids
    if len(set(case_ids)) != len(case_ids):
        raise DataValidationError(
            "benchmark_case_id_duplicate", "Benchmark case IDs must be unique."
        )
    if len(set(development)) != len(development) or len(set(sealed)) != len(sealed):
        raise DataValidationError(
            "benchmark_partition_duplicate", "Frozen benchmark partitions cannot repeat cases."
        )
    if set(development) | set(sealed) != set(case_ids) or set(development) & set(sealed):
        raise DataValidationError(
            "benchmark_partition_incomplete",
            "Frozen benchmark partitions must cover each case once.",
        )
    actual_clusters = {case.dependency_cluster_id for case in cases}
    if set(manifest.dependency_clusters) != actual_clusters:
        raise DataValidationError(
            "benchmark_cluster_set_changed", "Frozen dependency clusters changed."
        )


def _assert_temporal_cutoff(manifest: BenchmarkManifest, cases: Sequence[BenchmarkCase]) -> None:
    development = [case for case in cases if case.case_id in manifest.development_case_ids]
    sealed = [case for case in cases if case.case_id in manifest.sealed_case_ids]
    if not development or not sealed:
        raise DataValidationError(
            "benchmark_partition_empty", "Development and sealed partitions must both be non-empty."
        )
    if manifest.temporal_cutoff != max(case.event_time for case in development):
        raise DataValidationError(
            "benchmark_cutoff_mismatch", "Frozen temporal cutoff does not match development data."
        )
    if manifest.temporal_cutoff >= min(case.event_time for case in sealed):
        raise DataValidationError(
            "benchmark_temporal_leakage",
            "Every development event must precede every sealed event.",
        )


def _assert_clusters_separate(manifest: BenchmarkManifest, cases: Sequence[BenchmarkCase]) -> None:
    development = {
        case.dependency_cluster_id
        for case in cases
        if case.case_id in manifest.development_case_ids
    }
    sealed = {
        case.dependency_cluster_id for case in cases if case.case_id in manifest.sealed_case_ids
    }
    if development & sealed:
        raise DataValidationError(
            "benchmark_dependency_leakage", "A dependency cluster crosses the frozen split."
        )
