from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.persona_package import build_full_persona_package
from ynoy.full_persona.persona_package_store import FullPersonaPackageStore


def build_full_persona_package_handler(
    args: argparse.Namespace, context: CommandContext
) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    root = context.settings.require_private_root()
    pack = FullPersonaPackStore(root, synthetic=synthetic).read_pack(args.run_id)
    package = build_full_persona_package(pack)
    FullPersonaPackageStore(root, synthetic=synthetic).write_package(package)
    topic_states = {topic.key: topic.evidence_state for topic in package.dossier.topics}
    return {
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
        "persona_quality_claimed": False,
        "authority": "none",
        "action_status": "not_performed",
        "private_content_emitted": False,
    }
