from __future__ import annotations

from typing import Any, cast

from ynoy.full_persona.dossier import build_persona_dossier
from ynoy.models.full_persona_pack import PersonaLayerView, PersonaPack
from ynoy.models.persona_package import FullPersonaPackage, PersonaLayerSummary
from ynoy.util import canonical_sha256


def build_full_persona_package(pack: PersonaPack) -> FullPersonaPackage:
    """Bind the complete scan receipt, retained pack, dossier, and explicit unknowns."""
    dossier = build_persona_dossier(pack)
    summaries = tuple(_layer_summary(view) for view in pack.layers)
    package_id = canonical_sha256(
        {
            "protocol_version": "full-persona-package/0.1",
            "pack_sha256": pack.pack_sha256,
            "dossier_sha256": dossier.dossier_sha256,
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
        "topics": topics,
    }


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
