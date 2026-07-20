from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.persona_adjudication import adjudication_action_counts
from ynoy.full_persona.persona_package import (
    build_full_persona_package,
    render_persona_brain_atlas,
)
from ynoy.full_persona.persona_package_store import FullPersonaPackageStore
from ynoy.models.persona_package import FullPersonaPackage
from ynoy.util import sha256_text


def build_full_persona_package_handler(
    args: argparse.Namespace, context: CommandContext
) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    root = context.settings.require_private_root()
    pack = FullPersonaPackStore(root, synthetic=synthetic).read_pack(args.run_id)
    package = build_full_persona_package(pack)
    store = FullPersonaPackageStore(root, synthetic=synthetic)
    store.write_package(package)
    atlas = render_persona_brain_atlas(package)
    store.write_brain_atlas(package, atlas)
    return _package_summary(package, atlas)


def _package_summary(package: FullPersonaPackage, atlas: str) -> dict[str, object]:
    topic_states = {topic.key: topic.evidence_state for topic in package.dossier.topics}
    result: dict[str, object] = {
        "status": "full_persona_package_built",
        "package_id": package.package_id,
        "package_sha256": package.package_sha256,
        "source_scan_status": package.source_scan_status,
        "history_scope": package.history_scope,
        "processed_evidence_count": package.processed_evidence_count,
        "retained_atom_count": package.retained_atom_count,
        "unique_semantic_claim_count": package.unique_semantic_claim_count,
        "topic_states": topic_states,
        "retained_projection_exhaustive": False,
        "identity_fact_policy": package.identity_fact_policy,
        "calibration_status": package.calibration_status,
        "evolution_pattern_count": len(package.evolution.patterns),
        "evolution_total_pattern_candidate_count": (
            package.evolution.total_pattern_candidate_count
        ),
        "evolution_transition_count": len(package.evolution.transitions),
        "evolution_total_transition_candidate_count": (
            package.evolution.total_transition_candidate_count
        ),
        "evolution_status": "derived_unadopted",
        "evolution_use": "proposal_context_only",
        "persona_quality_claimed": False,
        "brain_atlas_built": True,
        "brain_atlas_sha256": sha256_text(atlas),
        "private_path_emitted": False,
        "authority": "none",
        "action_status": "not_performed",
        "private_content_emitted": False,
    }
    result.update(_adjudication_summary(package))
    return result


def _adjudication_summary(package: FullPersonaPackage) -> dict[str, object]:
    adjudication = package.adjudication
    return {
        "adjudication_recommendation_count": len(adjudication.recommendations),
        "adjudication_action_counts": adjudication_action_counts(adjudication),
        "represented_user_review": "not_performed",
        "verified_adoption_available": False,
        "adjudication_review_projection_status": adjudication.review_projection_status,
        "adjudication_review_projection_exhaustive": adjudication.review_projection_exhaustive,
        "adjudication_omitted_candidate_count": adjudication.omitted_candidate_count,
    }
