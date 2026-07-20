from __future__ import annotations

import json
from pathlib import Path

from ynoy.errors import DataValidationError
from ynoy.persona_study.storage_paths import reject_link_if_present, require_regular_file
from ynoy.util import atomic_write_bytes, canonical_sha256, sha256_file

_MARKER = b"ynoy-executive-spike-config-repair-v1\n"
_BROKEN = b'{"status":"broken","version":1}\n'
_FIXED = b'{"status":"fixed","version":1}\n'


def initialize_workspace(mission_root: Path) -> Path:
    """Create the only allowlisted D0 workspace and refuse an existing fixture."""
    workspace = mission_root / "workspace"
    if workspace.exists():
        raise DataValidationError(
            "executive_workspace_exists", "Synthetic workspace already exists."
        )
    workspace.mkdir(parents=True)
    atomic_write_bytes(workspace / ".ynoy-synthetic-repo", _MARKER)
    atomic_write_bytes(workspace / "config.json", _BROKEN)
    return workspace


def observe_failure(workspace: Path) -> tuple[str, str]:
    """Run the trusted D0 oracle before any patch is permitted."""
    if _read_config(workspace) != {"status": "broken", "version": 1}:
        raise DataValidationError(
            "executive_fixture_unexpected", "Synthetic fixture is not repairable."
        )
    return "Trusted synthetic config oracle observed status=broken.", workspace_digest(workspace)


def apply_known_patch(workspace: Path) -> tuple[str, str]:
    """Replace exactly the known D0 preimage; no model text or path enters this action."""
    config = _config_path(workspace)
    if config.read_bytes() != _BROKEN:
        raise DataValidationError(
            "executive_patch_preimage_mismatch", "Synthetic patch preimage changed."
        )
    atomic_write_bytes(config, _FIXED)
    return "Applied the allowlisted config-repair-v1 patch.", workspace_digest(workspace)


def verify_success(workspace: Path) -> tuple[str, str]:
    """Run the trusted D0 oracle after the fixed fixture is present."""
    if _read_config(workspace) != {"status": "fixed", "version": 1}:
        raise DataValidationError("executive_test_failed", "Synthetic config oracle did not pass.")
    return "Trusted synthetic config oracle passed status=fixed.", workspace_digest(workspace)


def workspace_digest(workspace: Path) -> str:
    """Return the digest of the two immutable D0 fixture inputs."""
    marker = workspace / ".ynoy-synthetic-repo"
    config = _config_path(workspace)
    require_regular_file(marker)
    require_regular_file(config)
    if marker.read_bytes() != _MARKER:
        raise DataValidationError(
            "executive_workspace_marker_invalid", "Synthetic workspace marker is invalid."
        )
    return canonical_sha256({"marker": sha256_file(marker), "config": sha256_file(config)})


def _read_config(workspace: Path) -> dict[str, object]:
    config = _config_path(workspace)
    try:
        value = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataValidationError(
            "executive_config_invalid", "Synthetic config is invalid."
        ) from exc
    if not isinstance(value, dict):
        raise DataValidationError("executive_config_invalid", "Synthetic config is invalid.")
    return value


def _config_path(workspace: Path) -> Path:
    reject_link_if_present(workspace)
    config = workspace / "config.json"
    reject_link_if_present(config)
    require_regular_file(config)
    return config
