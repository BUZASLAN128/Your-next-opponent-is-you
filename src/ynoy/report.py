from __future__ import annotations

from ynoy.benchmark import verify_benchmark_run
from ynoy.models import BenchmarkManifest, BenchmarkRun, InventoryManifest


def render_inventory_markdown(manifest: InventoryManifest) -> str:
    speaker_rows = "\n".join(
        f"| {speaker} | {count} |" for speaker, count in sorted(manifest.speaker_counts.items())
    )
    warnings = "\n".join(f"- `{warning}`" for warning in manifest.warnings) or "- None"
    return f"""# Corpus Inventory Report

This is a metadata-only inventory. It contains no conversation excerpts and derives no
personality claims.

| Field | Value |
|---|---:|
| Local only | true |
| External calls | 0 |
| Adapter | `{manifest.adapter}` |
| Parser | `{manifest.parser_version}` |
| Policy | `{manifest.policy_version}` |
| Source data class | `{manifest.source_data_class.value}` |
| Synthetic | `{str(manifest.synthetic).lower()}` |
| Archive bytes | {manifest.source_bytes} |
| Archive entries | {manifest.entry_count} |
| Conversations | {manifest.conversation_count} |
| Messages | {manifest.message_count} |
| Branches | {manifest.branch_count} |
| Malformed records | {manifest.malformed_record_count} |
| Excluded non-text parts | {manifest.excluded_content_part_count} |

## Speaker coverage

| Speaker | Events |
|---|---:|
{speaker_rows}

## Warnings

{warnings}

The manifest models source structure only. It is not a statement about the represented user's
identity, preferences, or decisions.
"""


def render_benchmark_markdown(manifest: BenchmarkManifest, run: BenchmarkRun) -> str:
    verify_benchmark_run(run)
    metric_rows = _benchmark_metric_rows(run)
    gates = "\n".join(f"- `{gate}`" for gate in run.fatal_gates) or "- None"
    header = (
        "| Regime / algorithm | N | Macro-F1 | Balanced accuracy | Coverage | "
        "Abstention | Decision loss | Fatal |"
    )
    return f"""# Scientific Core Benchmark Report

This report is a synthetic protocol/implementation check. Its evidence tier is
`{run.evidence_tier}`; it does not validate a real person's cognitive model.

| Field | Value |
|---|---:|
| Local only | `{str(run.local_only).lower()}` |
| External calls | {len(run.external_calls)} |
| Development cases | {len(manifest.development_case_ids)} |
| Sealed cases | {len(manifest.sealed_case_ids)} |
| Dependency clusters | {len(manifest.dependency_clusters)} |
| Temporal cutoff | `{manifest.temporal_cutoff.isoformat()}` |
| Acceptance status | `{run.acceptance_status}` |
| Run status | `{run.status}` |

No real acceptance threshold is claimed. Error costs and minimum practical improvement must be
calibrated with the represented user before a real sealed benchmark is opened.

## Metrics

{header}
|---|---:|---:|---:|---:|---:|---:|---:|
{metric_rows}

## Fatal gates

{gates}

Style similarity is not a success metric. Predictions have no action authority and no action
receipt.
"""


def _benchmark_metric_rows(run: BenchmarkRun) -> str:
    rows = []
    for group, metrics in sorted(run.metrics.items()):
        rows.append(
            "| {group} | {total} | {macro_f1:.3f} | {balanced:.3f} | {coverage:.3f} | "
            "{abstention:.3f} | {loss:.3f} | {fatal} |".format(
                group=group,
                total=int(metrics["total"]),
                macro_f1=float(metrics["macro_f1"]),
                balanced=float(metrics["balanced_accuracy"]),
                coverage=float(metrics["coverage"]),
                abstention=float(metrics["abstention_rate"]),
                loss=float(metrics["paired_decision_loss"]),
                fatal=int(metrics["fatal_gate_count"]),
            )
        )
    return "\n".join(rows)
