from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from support.persona_pack import built_pack

from ynoy.errors import DataValidationError
from ynoy.full_persona.dossier import build_persona_dossier
from ynoy.models.persona_dossier import PersonaDossier
from ynoy.util import canonical_sha256


def test_dossier_revalidates_tampered_pack_before_projection(tmp_path: Path) -> None:
    pack = built_pack(tmp_path)[3].model_copy(update={"pack_sha256": "f" * 64})

    with pytest.raises(DataValidationError):
        build_persona_dossier(pack)


def test_dossier_rejects_expired_canonical_pack(tmp_path: Path) -> None:
    pack = built_pack(tmp_path)[3]
    expired_base = pack.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    expired_payload = expired_base.model_dump(mode="json", exclude={"pack_sha256"})
    expired = expired_base.model_copy(update={"pack_sha256": canonical_sha256(expired_payload)})

    with pytest.raises(DataValidationError):
        build_persona_dossier(expired)


def test_dossier_model_rejects_reordered_topics_and_hash_tampering(tmp_path: Path) -> None:
    dossier = build_persona_dossier(built_pack(tmp_path)[3])
    reordered = dossier.model_copy(update={"topics": tuple(reversed(dossier.topics))})
    with pytest.raises(ValueError):
        PersonaDossier.model_validate(reordered.model_dump(mode="json"))

    tampered = dossier.model_copy(update={"dossier_sha256": "f" * 64})
    with pytest.raises(ValueError):
        PersonaDossier.model_validate(tampered.model_dump(mode="json"))
