from __future__ import annotations

import argparse
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.full_persona.deletion import delete_full_persona_run
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import FullCorpusHead, FullCorpusManifest
from ynoy.policy import assert_outside_git


def freeze_full_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source = _source(args.codex_root, synthetic)
    private_root = context.settings.require_private_root()
    manifest = freeze_full_corpus(source, private_root, args.source_study_id, synthetic=synthetic)
    head = FullPersonaStore(private_root, synthetic=synthetic).write_manifest(manifest)
    return _status(manifest, head, "full_persona_frozen")


def scan_full_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    source = _source(args.codex_root, synthetic)
    private_root = context.settings.require_private_root()
    head = scan_full_corpus(
        source,
        private_root,
        args.run_id,
        synthetic=synthetic,
        max_input_bytes=args.max_input_bytes,
    )
    manifest = FullPersonaStore(private_root, synthetic=synthetic).read_manifest(args.run_id)
    return _status(manifest, head, f"full_persona_{head.status}")


def full_persona_status(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = FullPersonaStore(context.settings.require_private_root(), synthetic=synthetic)
    manifest = store.read_manifest(args.run_id)
    head = store.read_head(args.run_id)
    verify_committed_run(store, manifest, head)
    return _status(manifest, head, "full_persona_status")


def delete_full_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    count = delete_full_persona_run(
        context.settings.require_private_root(), args.run_id, synthetic=bool(args.synthetic)
    )
    return {
        "status": "full_persona_generated_run_deleted",
        "deleted_artifact_count": count,
        "source_deleted": False,
        "physical_erase_claimed": False,
        "universal_erasure_claimed": False,
    }


def _source(value: str, synthetic: bool) -> Path:
    source = Path(value)
    if not synthetic:
        assert_outside_git(source)
    return source


def _status(manifest: FullCorpusManifest, head: FullCorpusHead, status: str) -> dict[str, object]:
    return {
        "status": status,
        "run_id": manifest.run_id,
        "head_sha256": head.head_sha256,
        "cursor_status": head.status,
        "file_progress": {"completed": head.file_index, "expected": manifest.expected_file_count},
        "byte_progress": {
            "processed": head.processed_input_bytes,
            "expected": manifest.expected_input_bytes,
        },
        "evidence_count": head.evidence_count,
        "quarantined_count": head.quarantined_count,
        "shard_count": head.shard_count,
        "output_bytes": head.output_bytes,
        "bounded_memory": True,
        "persona_pack_built": False,
        "persona_quality_claimed": False,
        "external_provider_used": False,
        "database_used": False,
        "automatic_core_promotion": False,
        "action_status": "not_performed",
    }
