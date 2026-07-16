from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ynoy.errors import DataValidationError

_SCOPES = ("annotator", "evaluator")


@dataclass(frozen=True, slots=True)
class StudyStoragePaths:
    root: Path

    def __post_init__(self) -> None:
        _require_real_directory(self.root)
        for path in (
            self.control_root,
            self.annotator_root,
            self.evaluator_root,
            self.tombstones,
            self.locks,
        ):
            _reject_link_if_present(path)

    @property
    def control_root(self) -> Path:
        return self.root / "persona-studies"

    @property
    def annotator_root(self) -> Path:
        return self.root / "persona-study-annotator"

    @property
    def evaluator_root(self) -> Path:
        return self.root / "persona-study-evaluator"

    @property
    def tombstones(self) -> Path:
        return self.root / "persona-study-tombstones"

    @property
    def locks(self) -> Path:
        return self.root / "persona-study-locks"

    def control_run(self, study_id: str) -> Path:
        _validate_study_id(study_id)
        return _safe_descendant(self.root, self.control_root / study_id)

    def index(self, study_id: str) -> Path:
        return _safe_descendant(self.root, self.control_run(study_id) / "index.json")

    def tombstone(self, proof_id: str) -> Path:
        _validate_study_id(proof_id)
        return _safe_descendant(self.root, self.tombstones / f"{proof_id}.json")

    def lock(self, study_id: str) -> Path:
        _validate_study_id(study_id)
        return _safe_descendant(self.root, self.locks / f"{study_id}.lock")

    def artifact(self, study_id: str, relative: str) -> Path:
        parts = Path(relative).parts
        if (
            not relative
            or "\\" in relative
            or Path(relative).is_absolute()
            or len(parts) < 2
            or parts[0] not in _SCOPES
            or ".." in parts
        ):
            raise DataValidationError(
                "persona_study_artifact_path_invalid",
                "Artifact paths must use an annotator/ or evaluator/ private scope.",
            )
        base = self.annotator_root if parts[0] == "annotator" else self.evaluator_root
        run = _safe_descendant(self.root, base / study_id)
        return _safe_descendant(self.root, run.joinpath(*parts[1:]))

    def run_paths(self, study_id: str) -> tuple[Path, Path, Path]:
        return (
            self.control_run(study_id),
            _safe_descendant(self.root, self.annotator_root / study_id),
            _safe_descendant(self.root, self.evaluator_root / study_id),
        )

    def run_is_absent(self, study_id: str) -> bool:
        return not any(_path_lexists(path) for path in self.run_paths(study_id))

    def ensure_run_absent(self, study_id: str) -> None:
        if not self.run_is_absent(study_id):
            raise DataValidationError(
                "persona_study_run_exists",
                "Refusing to overwrite a private persona-study run.",
            )

    def remove_empty_run(self, study_id: str) -> None:
        control, annotator, evaluator = self.run_paths(study_id)
        for run in (annotator, evaluator, control):
            _remove_empty_tree(run)


def require_regular_file(path: Path) -> None:
    if _is_link_like(path) or not path.is_file():
        raise DataValidationError(
            "persona_study_artifact_invalid", "A derived artifact is missing or linked."
        )


def reject_link_if_present(path: Path) -> None:
    _reject_link_if_present(path)


def _validate_study_id(study_id: str) -> None:
    if len(study_id) != 64 or any(char not in "0123456789abcdef" for char in study_id):
        raise DataValidationError("persona_study_id_invalid", "Study identifiers must be opaque.")


def _path_lexists(path: Path) -> bool:
    return path.exists() or _is_link_like(path)


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or bool(is_junction())


def _reject_link_if_present(path: Path) -> None:
    if _is_link_like(path):
        raise DataValidationError(
            "persona_study_link_rejected", "Private study storage cannot use links or junctions."
        )


def _require_real_directory(path: Path) -> None:
    if _is_link_like(path) or not path.is_dir():
        raise DataValidationError(
            "persona_study_root_invalid", "Private study root must be a real directory."
        )


def _safe_descendant(root: Path, candidate: Path) -> Path:
    _reject_link_if_present(root)
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise DataValidationError(
            "persona_study_path_escape", "Study path escaped private root."
        ) from exc
    current = root
    for part in relative.parts:
        current /= part
        _reject_link_if_present(current)
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(resolved_root):
        raise DataValidationError("persona_study_path_escape", "Study path escaped private root.")
    return resolved


def _remove_empty_tree(base: Path) -> None:
    if not base.exists():
        return
    _reject_link_if_present(base)
    directories = sorted(
        (item for item in base.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        _reject_link_if_present(directory)
        if not any(directory.iterdir()):
            directory.rmdir()
    if not any(base.iterdir()):
        base.rmdir()
