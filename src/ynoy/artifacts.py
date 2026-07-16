from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from ynoy.errors import DataValidationError
from ynoy.policy import require_private_root
from ynoy.util import atomic_write_bytes, canonical_json_bytes

T = TypeVar("T", bound=BaseModel)


class PrivateArtifactStore:
    def __init__(self, root: Path, *, real_data: bool):
        assessment = require_private_root(root, real_data=real_data)
        self.root = assessment.root
        self.storage_protection = "outside_git_local" if real_data else "synthetic_outside_git"

    def path_for(self, category: str, artifact_id: UUID | str, suffix: str = ".json") -> Path:
        safe_category = category.replace("\\", "_").replace("/", "_")
        safe_id = str(artifact_id).replace("\\", "_").replace("/", "_")
        path = (self.root / safe_category / f"{safe_id}{suffix}").resolve()
        if self.root not in path.parents:
            raise DataValidationError("artifact_path_escape", "Artifact path escaped private root.")
        return path

    def write_model(self, category: str, artifact_id: UUID | str, model: BaseModel) -> Path:
        path = self.path_for(category, artifact_id)
        atomic_write_bytes(path, canonical_json_bytes(model.model_dump(mode="json")))
        return path

    def write_json(self, category: str, artifact_id: UUID | str, value: object) -> Path:
        path = self.path_for(category, artifact_id)
        atomic_write_bytes(path, canonical_json_bytes(value))
        return path

    def write_markdown(self, category: str, artifact_id: UUID | str, value: str) -> Path:
        path = self.path_for(category, artifact_id, ".md")
        atomic_write_bytes(path, value.encode("utf-8"))
        return path

    def read_json(self, category: str, artifact_id: UUID | str) -> object:
        path = self.path_for(category, artifact_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise DataValidationError(
                "artifact_not_found", f"Private artifact {artifact_id} was not found."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise DataValidationError(
                "artifact_invalid", f"Private artifact {artifact_id} is invalid."
            ) from exc

    def read_model(self, category: str, artifact_id: UUID | str, model_type: type[T]) -> T:
        path = self.path_for(category, artifact_id)
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
            return model_type.model_validate(raw)
        except FileNotFoundError as exc:
            raise DataValidationError(
                "artifact_not_found", f"Private artifact {artifact_id} was not found."
            ) from exc
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise DataValidationError(
                "artifact_invalid", f"Private artifact {artifact_id} is invalid."
            ) from exc

    def delete_if_exists(
        self, category: str, artifact_id: UUID | str, suffix: str = ".json"
    ) -> bool:
        path = self.path_for(category, artifact_id, suffix)
        if not path.exists():
            return False
        if not path.is_file():
            raise DataValidationError(
                "artifact_not_regular_file", "Refusing to erase a non-file artifact path."
            )
        path.unlink()
        return True
