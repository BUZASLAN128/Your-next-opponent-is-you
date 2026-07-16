from __future__ import annotations

from pathlib import Path

import pytest

from ynoy.config import Settings
from ynoy.doctor import run_doctor
from ynoy.errors import PolicyViolation
from ynoy.storage import Database

pytestmark = pytest.mark.integration


def test_database_status_exposes_superuser_and_doctor_blocks_real_ready(
    test_database: Database,
    test_database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = test_database.status()
    assert status["database_user"] == "ynoy"
    assert status["database_user_is_superuser"] is True
    assert status["audit_can_insert"] is True
    assert status["audit_can_update"] is True
    assert status["audit_can_delete"] is True
    assert status["audit_can_truncate"] is True
    with pytest.raises(PolicyViolation) as blocked:
        test_database.require_restricted_runtime()
    assert blocked.value.code == "database_superuser_blocked_for_real_data"
    settings = Settings(
        private_root=tmp_path / "private-root",
        postgres_data_path=None,
        database_url=test_database_url,
        local_reasoner_url=None,
        local_model_attested=False,
        local_reasoner_model="fixture-model",
        embedding_model="fixture-embedding",
    )
    monkeypatch.setattr(
        "ynoy.doctor._private_root_check",
        lambda _: {
            "name": "private_root",
            "status": "pass",
            "detail": "outside_git",
            "synthetic_ready": True,
            "real_data_ready": True,
        },
    )
    result = run_doctor(settings, repository_root=Path(__file__).resolve().parents[1])
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["database_role"]["status"] == "fail"
    assert checks["database_role"]["detail"] == "unsafe_audit_or_role_privileges"
    assert result["synthetic_ready"] is True
    assert result["real_data_ready"] is False
