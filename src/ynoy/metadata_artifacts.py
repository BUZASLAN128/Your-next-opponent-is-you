from __future__ import annotations

from pathlib import Path

from ynoy.errors import DataValidationError
from ynoy.models import CodexMetadataInventory
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes


class PrivateMetadataInventoryStore:
    """Write-only store for metadata inventory; it cannot persist corpus content."""

    def __init__(self, root: Path, *, synthetic: bool):
        assessment = require_private_root(root, real_data=not synthetic)
        self.root = assessment.root
        self.storage_protection = "synthetic_outside_git" if synthetic else "outside_git_local"

    def write_manifest(self, manifest: CodexMetadataInventory) -> Path:
        if type(manifest) is not CodexMetadataInventory:
            raise DataValidationError(
                "metadata_inventory_model_required",
                "Metadata inventory storage accepts only its exact manifest contract.",
            )
        from ynoy.corpus.codex import verify_codex_metadata_inventory

        verify_codex_metadata_inventory(manifest)
        artifact_id = manifest.record_id
        safe_id = str(artifact_id).replace("\\", "_").replace("/", "_")
        path = (self.root / "codex-metadata-inventory" / f"{safe_id}.json").resolve()
        if self.root not in path.parents:
            raise DataValidationError("artifact_path_escape", "Artifact path escaped private root.")
        atomic_write_bytes(path, canonical_json_bytes(manifest.model_dump(mode="json")))
        return path
