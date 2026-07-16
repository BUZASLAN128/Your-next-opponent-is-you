from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

Check = dict[str, object]


def repository_check(root: Path) -> Check:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _unreadable()
    if result.returncode != 0:
        return {"name": "public_repository_boundary", "status": "fail", "detail": "not_git"}
    tracked = [item.decode("utf-8", "replace") for item in result.stdout.split(b"\0") if item]
    forbidden = {path for path in tracked if looks_private(path)}
    manifest_paths = _tracked_codex_manifests(root)
    if manifest_paths is None:
        return _unreadable()
    forbidden.update(manifest_paths)
    return {
        "name": "public_repository_boundary",
        "status": "fail" if forbidden else "pass",
        "detail": "private-looking tracked artifacts found" if forbidden else "clean",
        "forbidden_count": len(forbidden),
    }


def _unreadable() -> Check:
    return {"name": "public_repository_boundary", "status": "fail", "detail": "unreadable"}


def _tracked_codex_manifests(root: Path) -> set[str] | None:
    patterns = (
        r'"adapter"[[:space:]]*:[[:space:]]*"codex_local_sessions_metadata"',
        r'"metadata_snapshot_sha256"[[:space:]]*:',
        r'"content_fields_copied"[[:space:]]*:',
    )
    matches: list[set[str]] = []
    for pattern in patterns:
        result = _git(root, "grep", "--cached", "-IlzE", pattern)
        if result is None or result.returncode not in {0, 1}:
            return None
        matches.append(
            {item.decode("utf-8", "replace") for item in result.stdout.split(b"\0") if item}
        )
    manifests: set[str] = set()
    for path in set.intersection(*matches):
        looks_like_manifest = _index_looks_like_json_manifest(root, path)
        if looks_like_manifest is None:
            return None
        if looks_like_manifest:
            manifests.add(path)
    return manifests


def _index_looks_like_json_manifest(root: Path, path: str) -> bool | None:
    size = _git(root, "cat-file", "-s", f":{path}")
    if size is None or size.returncode != 0:
        return None
    try:
        blob_size = int(size.stdout.strip())
    except ValueError:
        return None
    if blob_size > 1_048_576:
        return True
    content = _git(root, "show", f":{path}")
    if content is None or content.returncode != 0:
        return None
    prefix = content.stdout.lstrip(b"\xef\xbb\xbf \t\r\n")
    return prefix.startswith(b"{")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def looks_private(value: str) -> bool:
    path = PurePosixPath(value)
    blocked_roots = {
        "archived_sessions",
        "codex-metadata-inventory",
        "data",
        "manifests",
        "models",
        "private",
        "reports",
        "sessions",
    }
    blocked_suffixes = {
        ".db",
        ".gguf",
        ".jsonl",
        ".parquet",
        ".safetensors",
        ".sqlite",
        ".sqlite3",
        ".zip",
    }
    blocked_names = {"conversations.json"}
    parts = tuple(part.casefold() for part in path.parts)
    public_model_source = (
        len(parts) == 4
        and parts[:3] == ("src", "ynoy", "models")
        and path.suffix.casefold() == ".py"
    )
    private_part = not public_model_source and any(
        part in blocked_roots or part.startswith("backup") for part in parts[:-1]
    )
    return (
        private_part
        or path.suffix.casefold() in blocked_suffixes
        or path.name.casefold() in blocked_names
    )
