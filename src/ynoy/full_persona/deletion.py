from __future__ import annotations

import os
from pathlib import Path

from ynoy.errors import DataValidationError
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.store import FullPersonaStore
from ynoy.persona_study.storage_paths import reject_link_if_present


def delete_full_persona_run(private_root: Path, run_id: str, *, synthetic: bool) -> int:
    """Delete one generated private run without claiming source or physical erasure."""
    store = FullPersonaStore(private_root, synthetic=synthetic)
    with store.lock(run_id):
        run = store.run_path(run_id)
        pack_run = FullPersonaPackStore(private_root, synthetic=synthetic).run_path(run_id)
        staging = store.staging_run_path(run_id)
        if not run.is_dir() and not pack_run.is_dir() and not staging.is_dir():
            raise DataValidationError(
                "full_persona_run_not_found", "The private full-persona run was not found."
            )
        deleted = 0
        if pack_run.exists():
            deleted += _delete_tree(pack_run)
        if run.exists():
            deleted += _delete_tree(run)
        if staging.exists():
            deleted += _delete_tree(staging)
        if run.exists() or staging.exists() or pack_run.exists():
            raise DataValidationError(
                "full_persona_delete_incomplete",
                "The generated full-persona run was not deleted completely.",
            )
        return deleted


def _delete_tree(root: Path) -> int:
    reject_link_if_present(root)
    resolved = root.resolve(strict=True)
    deleted = _delete_children(resolved)
    resolved.rmdir()
    return deleted


def _delete_children(root: Path) -> int:
    deleted = 0
    with os.scandir(root) as entries:
        children = sorted(entries, key=lambda item: item.name.casefold())
    for entry in children:
        path = Path(entry.path)
        reject_link_if_present(path)
        if entry.is_file(follow_symlinks=False):
            path.unlink()
            deleted += 1
        elif entry.is_dir(follow_symlinks=False):
            deleted += _delete_children(path)
            path.rmdir()
        else:
            raise DataValidationError(
                "full_persona_delete_special_file",
                "Generated full-persona storage contains an unsupported file type.",
            )
    return deleted
