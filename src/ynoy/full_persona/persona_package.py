from __future__ import annotations

from typing import Any, cast

from ynoy.full_persona.dossier import build_persona_dossier
from ynoy.full_persona.persona_adjudication import (
    adjudication_action_counts,
    build_persona_adjudication,
)
from ynoy.full_persona.persona_evolution import build_persona_evolution
from ynoy.models.full_persona_pack import PersonaLayerView, PersonaPack
from ynoy.models.persona_package import FullPersonaPackage, PersonaLayerSummary
from ynoy.util import canonical_sha256


def build_full_persona_package(pack: PersonaPack) -> FullPersonaPackage:
    """Bind the complete scan receipt, retained pack, dossier, and explicit unknowns."""
    dossier = build_persona_dossier(pack)
    evolution = build_persona_evolution(pack)
    adjudication = build_persona_adjudication(evolution)
    summaries = tuple(_layer_summary(view) for view in pack.layers)
    package_id = canonical_sha256(
        {
            "protocol_version": "full-persona-package/0.3",
            "pack_sha256": pack.pack_sha256,
            "dossier_sha256": dossier.dossier_sha256,
            "evolution_sha256": evolution.evolution_sha256,
            "adjudication_sha256": adjudication.adjudication_sha256,
        }
    )
    payload: dict[str, object] = {
        "package_id": package_id,
        "pack_id": pack.pack_id,
        "pack_sha256": pack.pack_sha256,
        "source_run_id": pack.source_run_id,
        "source_manifest_sha256": pack.source_manifest_sha256,
        "source_head_sha256": pack.source_head_sha256,
        "source_head_revision": pack.source_head_revision,
        "expires_at": pack.expires_at,
        "data_class": pack.data_class,
        "synthetic": pack.synthetic,
        "processed_evidence_count": pack.processed_evidence_count,
        "retained_atom_count": pack.retained_atom_count,
        "unique_semantic_claim_count": sum(item.unique_semantic_claim_count for item in summaries),
        "layer_summaries": summaries,
        "dossier": dossier,
        "evolution": evolution,
        "adjudication": adjudication,
    }
    draft = cast(Any, FullPersonaPackage).model_construct(**payload, package_sha256="0" * 64)
    canonical = draft.model_dump(mode="json", exclude={"package_sha256"})
    return FullPersonaPackage.model_validate(
        {**canonical, "package_sha256": canonical_sha256(canonical)}
    )


def persona_prompt_profile(package: FullPersonaPackage) -> dict[str, object]:
    """Project all fourteen dossier sections into a bounded generation profile."""
    topics: list[dict[str, object]] = []
    for topic in package.dossier.topics:
        item: dict[str, object] = {
            "topic": topic.key,
            "state": topic.evidence_state,
            "candidate_count": topic.total_candidate_count,
            "unknown": topic.evidence_state == "unknown",
        }
        topics.append(item)
    return {
        "history_scope": package.history_scope,
        "source_scan_status": package.source_scan_status,
        "retained_projection_exhaustive": package.retained_projection_exhaustive,
        "identity_fact_policy": package.identity_fact_policy,
        "calibration_status": package.calibration_status,
        "evolution": {
            "pattern_count": len(package.evolution.patterns),
            "total_pattern_candidate_count": package.evolution.total_pattern_candidate_count,
            "transition_count": len(package.evolution.transitions),
            "total_transition_candidate_count": (
                package.evolution.total_transition_candidate_count
            ),
            "status": "derived_unadopted",
            "use": "proposal_context_only",
        },
        "topics": topics,
    }


def render_persona_brain_atlas(package: FullPersonaPackage) -> str:
    """Render a private, receipt-bound atlas without adding inferred identity facts."""
    lines = [
        "# Full Persona Brain Atlas",
        "",
        f"- Source scan: {package.source_scan_status}",
        f"- Processed evidence: {package.processed_evidence_count}",
        f"- Retained atoms: {package.retained_atom_count}",
        f"- Unique semantic claims: {package.unique_semantic_claim_count}",
        "- Persona quality: not claimed",
        "- Authority: none",
    ]
    for topic in package.dossier.topics:
        lines.extend(("", f"## {topic.key}", "", f"- State: {topic.evidence_state}"))
        lines.append(f"- Total candidates: {topic.total_candidate_count}")
        for signal in topic.style_signals:
            lines.append(f"- Style signal: {signal.name} - {signal.guidance}")
            lines.extend(_receipt_lines(signal.supports))
        for candidate in topic.candidates:
            lines.extend(
                (
                    "",
                    f"### Candidate {candidate.atom_id[:12]}",
                    "",
                    f"- Truth status: {candidate.truth_status}",
                    f"- Source role: {candidate.source_role}",
                    f"- Claim: {_single_line(candidate.claim)}",
                )
            )
            lines.extend(f"- Receipt: {item}" for item in candidate.evidence_receipts)
        lines.extend(f"- Unknown: {item}" for item in topic.unknowns)
    lines.extend(_evolution_lines(package))
    lines.extend(_adjudication_lines(package))
    lines.extend(
        (
            "",
            "## Global safety state",
            "",
            "- Semantic adoption: not_established",
            "- Automatic core promotion: false",
            "- Send/execute authority: none",
        )
    )
    return "\n".join(lines) + "\n"


def _evolution_lines(package: FullPersonaPackage) -> list[str]:
    lines = ["", "## Evolution", "", "- Status: derived_unadopted"]
    lines.extend(("- Use: proposal_context_only", "- Scope: not_established"))
    lines.append(f"- Retained patterns: {len(package.evolution.patterns)}")
    lines.append(f"- Total pattern candidates: {package.evolution.total_pattern_candidate_count}")
    lines.append(f"- Retained transitions: {len(package.evolution.transitions)}")
    lines.append(
        f"- Total transition candidates: {package.evolution.total_transition_candidate_count}"
    )
    for pattern in package.evolution.patterns:
        lines.extend(
            (
                "",
                f"### Pattern {pattern.key}",
                "",
                f"- Evidence count: {pattern.evidence_count}",
                f"- Distinct atoms: {pattern.distinct_atom_count}",
                f"- Strength band: {pattern.evidence_strength}",
                f"- Guidance: {pattern.guidance}",
            )
        )
        lines.extend(f"- Receipt: {item.evidence_receipt}" for item in pattern.evidence_refs)
    for transition in package.evolution.transitions:
        lines.extend(
            (
                "",
                f"### Transition {transition.dimension}",
                "",
                f"- From: {transition.from_state}",
                f"- To: {transition.to_state}",
                f"- At: {transition.transition_at.isoformat()}",
                f"- From receipt: {transition.from_evidence.evidence_receipt}",
                f"- To receipt: {transition.to_evidence.evidence_receipt}",
            )
        )
    lines.extend(f"- Unknown: {item}" for item in package.evolution.unknowns)
    return lines


def _receipt_lines(supports: tuple[object, ...]) -> list[str]:
    return [
        f"- Receipt: {receipt}"
        for support in supports
        for receipt in getattr(support, "evidence_receipts", ())
    ]


def _adjudication_lines(package: FullPersonaPackage) -> list[str]:
    profile = package.adjudication
    lines = ["", "## System adjudication", ""]
    lines.append(f"- Recommendations: {len(profile.recommendations)}")
    lines.append("- Represented-user review: not_performed")
    lines.append("- Verified adoption: unavailable")
    lines.append(f"- Review projection: {profile.review_projection_status}")
    lines.append(
        f"- Review projection exhaustive: {str(profile.review_projection_exhaustive).lower()}"
    )
    lines.append(f"- Omitted source candidates: {profile.omitted_candidate_count}")
    lines.append("- Authority: none")
    for action, count in adjudication_action_counts(profile).items():
        lines.append(f"- {action}: {count}")
    return lines


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _layer_summary(view: PersonaLayerView) -> PersonaLayerSummary:
    semantic = {atom.semantic_key for atom in view.atoms}
    observations = sum(atom.observation_count for atom in view.atoms)
    return PersonaLayerSummary(
        layer=view.layer,
        retained_atom_count=len(view.atoms),
        unique_semantic_claim_count=len(semantic),
        represented_observation_count=observations,
        duplicate_observation_count=max(0, observations - len(semantic)),
    )
