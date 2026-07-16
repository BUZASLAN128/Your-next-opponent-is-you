from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ynoy.artifacts import PrivateArtifactStore
from ynoy.config import Settings
from ynoy.database_policy import require_local_database
from ynoy.metadata_artifacts import PrivateMetadataInventoryStore
from ynoy.policy import require_private_root
from ynoy.storage import Database


@dataclass(frozen=True, slots=True)
class CommandContext:
    settings: Settings
    repository_root: Path

    def artifacts(self, *, synthetic: bool) -> PrivateArtifactStore:
        root = self.settings.require_private_root()
        return PrivateArtifactStore(root, real_data=not synthetic)

    def review_artifacts(self, *, synthetic: bool) -> PrivateArtifactStore:
        root = self.settings.require_private_root()
        return PrivateArtifactStore(root, real_data=not synthetic)

    def metadata_inventory_artifacts(self, *, synthetic: bool) -> PrivateMetadataInventoryStore:
        root = self.settings.require_private_root()
        return PrivateMetadataInventoryStore(root, synthetic=synthetic)

    def database(self, *, synthetic: bool) -> Database:
        root = self.settings.require_private_root()
        require_private_root(root, real_data=not synthetic)
        database_url = self.settings.require_database_url()
        require_local_database(
            database_url,
            private_root=root,
            postgres_data_path=self.settings.postgres_data_path,
            real_data=not synthetic,
        )
        database = Database(database_url)
        database.require_current_schema()
        if not synthetic:
            database.require_restricted_runtime()
        return database

    def setup_database(self) -> Database:
        database_url = self.settings.require_database_url()
        root = self.settings.private_root or self.repository_root
        require_local_database(
            database_url,
            private_root=root,
            postgres_data_path=self.settings.postgres_data_path,
            real_data=False,
        )
        return Database(database_url)
