from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ynoy.constants import DEFAULT_EMBEDDING_MODEL, DEFAULT_LOCAL_REASONER_MODEL
from ynoy.errors import PolicyViolation


@dataclass(frozen=True, slots=True)
class Settings:
    private_root: Path | None
    postgres_data_path: Path | None
    database_url: str | None
    local_reasoner_url: str | None
    local_model_attested: bool
    local_reasoner_model: str
    embedding_model: str
    local_reasoner_revision: str | None = None
    local_reasoner_artifact_sha256: str | None = None
    local_reasoner_model_explicit: bool = False

    @classmethod
    def from_environment(
        cls,
        *,
        private_root: Path | None = None,
        database_url: str | None = None,
    ) -> Settings:
        raw_root = os.environ.get("YNOY_PRIVATE_ROOT")
        raw_postgres_path = os.environ.get("YNOY_POSTGRES_DATA_PATH")
        resolved_root = private_root or (Path(raw_root) if raw_root else None)
        return cls(
            private_root=resolved_root.expanduser().resolve() if resolved_root else None,
            postgres_data_path=(
                Path(raw_postgres_path).expanduser().resolve() if raw_postgres_path else None
            ),
            database_url=database_url or os.environ.get("YNOY_DATABASE_URL"),
            local_reasoner_url=os.environ.get("YNOY_LOCAL_REASONER_URL"),
            local_model_attested=(
                os.environ.get("YNOY_LOCAL_MODEL_ATTESTED", "false").casefold() == "true"
            ),
            local_reasoner_model=os.environ.get(
                "YNOY_LOCAL_REASONER_MODEL", DEFAULT_LOCAL_REASONER_MODEL
            ),
            embedding_model=os.environ.get("YNOY_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            local_reasoner_revision=os.environ.get("YNOY_LOCAL_REASONER_REVISION"),
            local_reasoner_artifact_sha256=os.environ.get("YNOY_LOCAL_REASONER_ARTIFACT_SHA256"),
            local_reasoner_model_explicit=bool(os.environ.get("YNOY_LOCAL_REASONER_MODEL")),
        )

    def require_private_root(self) -> Path:
        if self.private_root is None:
            raise PolicyViolation(
                "private_root_required",
                "Set --private-root or YNOY_PRIVATE_ROOT to a private path outside Git.",
            )
        return self.private_root

    def require_database_url(self) -> str:
        if not self.database_url:
            raise PolicyViolation(
                "database_url_required",
                "Set --database-url or YNOY_DATABASE_URL for this command.",
            )
        return self.database_url
