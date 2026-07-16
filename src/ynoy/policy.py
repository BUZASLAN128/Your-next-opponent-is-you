from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ynoy.errors import PolicyViolation
from ynoy.models import DataClass, EgressEnvelope


@dataclass(frozen=True, slots=True)
class PrivateRootAssessment:
    root: Path
    outside_git: bool

    @property
    def synthetic_ready(self) -> bool:
        return self.outside_git

    @property
    def real_data_ready(self) -> bool:
        return self.outside_git


def _git_ancestor(path: Path) -> Path | None:
    candidate = path.resolve()
    if not candidate.exists():
        candidate = candidate.parent
    for ancestor in (candidate, *candidate.parents):
        if (ancestor / ".git").exists():
            return ancestor
    return None


def assert_outside_git(path: Path) -> None:
    root = path.resolve()
    ancestor = _git_ancestor(root)
    if ancestor is not None:
        raise PolicyViolation(
            "private_root_inside_git",
            "Private identity artifacts must be stored outside every Git worktree.",
        )


def assess_private_root(root: Path) -> PrivateRootAssessment:
    resolved = root.expanduser().resolve()
    return PrivateRootAssessment(root=resolved, outside_git=_git_ancestor(resolved) is None)


def require_private_root(root: Path, *, real_data: bool) -> PrivateRootAssessment:
    _ = real_data
    assessment = assess_private_root(root)
    if not assessment.outside_git:
        assert_outside_git(root)
    assessment.root.mkdir(parents=True, exist_ok=True)
    return assessment


def require_private_source(source: Path, private_root: Path) -> Path:
    """Require a real identity input to live inside the explicit outside-Git root."""
    assert_outside_git(source)
    assessment = require_private_root(private_root, real_data=True)
    return _resolve_private_source(source, assessment)


def _resolve_private_source(source: Path, assessment: PrivateRootAssessment) -> Path:
    try:
        resolved = source.expanduser().resolve(strict=True)
    except OSError as exc:
        raise PolicyViolation(
            "private_source_unavailable", "Private identity source is unavailable."
        ) from exc
    if not resolved.is_file():
        raise PolicyViolation("private_source_not_file", "Private identity source is not a file.")
    if not resolved.is_relative_to(assessment.root):
        raise PolicyViolation(
            "private_source_outside_root",
            "Private identity sources must be inside the authorized private root.",
        )
    return resolved


def is_loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}


def authorize_egress(envelope: EgressEnvelope, *, adapter_is_local: bool) -> None:
    if adapter_is_local:
        return
    blocked = envelope.data_classes - {DataClass.PUBLIC_SYNTHETIC}
    if blocked:
        raise PolicyViolation(
            "persona_egress_blocked",
            "V1 external adapters accept public or synthetic D0 data only.",
            details={"blocked_classes": sorted(item.value for item in blocked)},
        )
    if envelope.retention_assumption.casefold() in {"", "unknown", "unspecified"}:
        raise PolicyViolation(
            "unknown_external_retention",
            "External calls require an explicit retention assumption.",
        )
