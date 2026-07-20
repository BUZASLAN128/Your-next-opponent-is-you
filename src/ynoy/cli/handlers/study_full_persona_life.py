from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.full_persona.life_profile import build_verified_life_profile
from ynoy.full_persona.life_profile_store import FullPersonaLifeProfileStore
from ynoy.full_persona.store import FullPersonaStore


def build_full_persona_life_profile(
    args: argparse.Namespace, context: CommandContext
) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    root = context.settings.require_private_root()
    source = FullPersonaStore(root, synthetic=synthetic)
    manifest = source.read_manifest(args.run_id)
    head = source.read_head(args.run_id)
    profile = build_verified_life_profile(source, manifest, head)
    FullPersonaLifeProfileStore(root, synthetic=synthetic).write(profile)
    return {
        "status": "full_persona_life_profile_built",
        "source_scan_status": profile.source_scan_status,
        "matcher_coverage": profile.matcher_coverage,
        "scanned_evidence_count": profile.scanned_evidence_count,
        "topic_states": {item.key: item.evidence_state for item in profile.topics},
        "topic_candidate_counts": {
            item.key: item.unique_candidate_count for item in profile.topics
        },
        "semantic_exhaustive": False,
        "identity_fact_policy": profile.identity_fact_policy,
        "persona_quality_claimed": False,
        "authority": "none",
        "private_content_emitted": False,
    }
