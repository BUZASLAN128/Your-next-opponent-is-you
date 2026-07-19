from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.full_persona.pack_builder import build_deterministic_pack
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.retrieval import retrieve_persona_atoms
from ynoy.models.full_persona_pack import PersonaPackBuildConfig


def build_full_persona_pack(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    root = context.settings.require_private_root()
    config = PersonaPackBuildConfig(
        max_atoms_per_layer=args.max_atoms_per_layer,
        max_excerpt_chars=args.max_excerpt_chars,
    )
    pack = build_deterministic_pack(root, args.run_id, synthetic=synthetic, config=config)
    receipt = FullPersonaPackStore(root, synthetic=synthetic).write_pack(pack)
    return {
        "status": "full_persona_pack_built",
        "run_id": pack.source_run_id,
        "pack_id": pack.pack_id,
        "pack_sha256": pack.pack_sha256,
        "receipt_sha256": receipt.receipt_sha256,
        "processed_evidence_count": pack.processed_evidence_count,
        "retained_atom_count": pack.retained_atom_count,
        "layer_counts": {view.layer.value: len(view.atoms) for view in pack.layers},
        "unknowns": pack.unknowns,
        "bounded_memory": True,
        "model_enrichment": pack.model_enrichment,
        "calibration_status": pack.calibration_status,
        "persona_quality_claimed": False,
        "automatic_core_promotion": False,
        "action_status": "not_performed",
    }


def query_full_persona_pack(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = FullPersonaPackStore(context.settings.require_private_root(), synthetic=synthetic)
    pack = store.read_pack(args.run_id)
    atoms = retrieve_persona_atoms(pack, args.query, top_k=args.top_k)
    return {
        "status": "unvalidated_persona_retrieval_preview",
        "run_id": pack.source_run_id,
        "pack_id": pack.pack_id,
        "query": args.query,
        "matches": [
            {
                "atom_id": atom.atom_id,
                "layer": atom.layer.value,
                "claim": atom.claim,
                "basis": atom.basis.value,
                "status": atom.status.value,
                "source_role": atom.source_role.value if atom.source_role else None,
                "adopted": atom.adopted,
                "semantic_adoption": atom.semantic_adoption,
                "core_eligible": atom.core_eligible,
                "evidence_receipts": atom.evidence_receipts,
            }
            for atom in atoms
        ],
        "judgment_basis": "abstention",
        "calibration_status": pack.calibration_status,
        "unknowns": pack.unknowns,
        "authority": "none",
        "action_status": "not_performed",
        "send_enabled": False,
        "execute_enabled": False,
        "automatic_core_promotion": False,
    }
