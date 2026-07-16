from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ynoy.config import Settings
from ynoy.database_policy import LIBPQ_ENVIRONMENT_OVERRIDES
from ynoy.doctor import _looks_private, _repository_check, run_doctor


def _settings(tmp_path: Path, database_url: str) -> Settings:
    return Settings(
        private_root=tmp_path / "private-root",
        postgres_data_path=None,
        database_url=database_url,
        local_reasoner_url=None,
        local_model_attested=False,
        local_reasoner_model="fixture-model",
        embedding_model="fixture-embedding",
    )


def _ready_private_root(_: Settings) -> dict[str, object]:
    return {
        "name": "private_root",
        "status": "pass",
        "detail": "outside_git",
        "synthetic_ready": True,
        "real_data_ready": True,
    }


def _git(repository: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("relative_path", "expected_private"),
    [
        ("nested/sessions/metadata.txt", True),
        ("nested/archived_sessions/metadata.txt", True),
        ("nested/backup-2026/metadata.txt", True),
        ("nested/backups-2026/metadata.txt", True),
        ("nested/codex-metadata-inventory/metadata.txt", True),
        ("nested/data/metadata.txt", True),
        ("nested/private/metadata.txt", True),
        ("nested/reports/metadata.txt", True),
        ("nested/models/metadata.txt", True),
        ("src/ynoy/models/base.py", False),
    ],
)
def test_git_ignore_matches_doctor_private_classification(
    relative_path: str, expected_private: bool
) -> None:
    repository = Path(__file__).resolve().parents[1]
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", relative_path],
        cwd=repository,
        check=False,
        capture_output=True,
        timeout=10,
    )

    assert ignored.returncode == (0 if expected_private else 1)
    assert _looks_private(relative_path) is expected_private


def test_repository_gate_rejects_staged_manifest_renamed_to_safe_text_path(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    original = repository / "codex-metadata-inventory" / "manifest.json"
    original.parent.mkdir()
    original.write_text(
        json.dumps(
            {
                "adapter": "codex_local_sessions_metadata",
                "metadata_snapshot_sha256": "0" * 64,
                "content_fields_copied": False,
            }
        ),
        encoding="utf-8",
    )
    _git(repository, "add", "--force", "--", "codex-metadata-inventory/manifest.json")
    safe = repository / "docs" / "cache" / "item.txt"
    safe.parent.mkdir(parents=True)
    _git(
        repository,
        "mv",
        "--force",
        "--",
        original.relative_to(repository).as_posix(),
        safe.relative_to(repository).as_posix(),
    )
    safe.write_text('{"title":"unstaged ordinary working copy"}', encoding="utf-8")

    result = _repository_check(repository)

    assert result["status"] == "fail"
    assert result["detail"] == "private-looking tracked artifacts found"
    assert result["forbidden_count"] == 1


def test_repository_content_gate_allows_normal_staged_json(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    document = repository / "docs" / "cache" / "item.json"
    document.parent.mkdir(parents=True)
    document.write_text('{"title":"ordinary document","items":[1,2]}', encoding="utf-8")
    _git(repository, "add", "--", document.relative_to(repository).as_posix())

    result = _repository_check(repository)

    assert result["status"] == "pass"
    assert result["detail"] == "clean"
    assert result["forbidden_count"] == 0


def test_doctor_rejects_remote_database_before_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_calls = 0

    def unexpected_database(_: str) -> None:
        nonlocal database_calls
        database_calls += 1
        raise AssertionError("remote database must not be constructed")

    monkeypatch.setattr("ynoy.doctor.Database", unexpected_database)
    monkeypatch.setattr("ynoy.doctor._private_root_check", _ready_private_root)
    settings = _settings(tmp_path, "postgresql://user:secret@db.example/ynoy")

    result = run_doctor(settings, repository_root=Path(__file__).resolve().parents[1])

    checks = {check["name"]: check for check in result["checks"]}
    assert database_calls == 0
    assert checks["database_boundary"]["detail"] == "database_not_loopback"
    assert checks["database_version"]["detail"] == "database_not_loopback"
    assert checks["database_role"]["detail"] == "database_not_loopback"
    assert result["synthetic_ready"] is False
    assert result["real_data_ready"] is False


def test_doctor_rejects_connection_options_before_database_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_calls = 0

    def unexpected_database(_: str) -> None:
        nonlocal database_calls
        database_calls += 1
        raise AssertionError("blocked connection options must not construct Database")

    monkeypatch.setattr("ynoy.doctor.Database", unexpected_database)
    monkeypatch.setattr("ynoy.doctor._private_root_check", _ready_private_root)
    settings = _settings(
        tmp_path,
        "postgresql://user:secret@127.0.0.1:55432/ynoy?application_name=ynoy",
    )

    result = run_doctor(settings, repository_root=Path(__file__).resolve().parents[1])

    checks = {check["name"]: check for check in result["checks"]}
    assert database_calls == 0
    assert checks["database_boundary"]["detail"] == "database_connection_options_blocked"
    assert checks["database_version"]["detail"] == "database_connection_options_blocked"
    assert checks["database_role"]["detail"] == "database_connection_options_blocked"
    assert result["synthetic_ready"] is False
    assert result["real_data_ready"] is False


def test_doctor_rejects_libpq_environment_before_database_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_calls = 0

    def unexpected_database(_: str) -> None:
        nonlocal database_calls
        database_calls += 1
        raise AssertionError("blocked libpq environment must not construct Database")

    for variable in LIBPQ_ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("PGSERVICE", "production-service")
    monkeypatch.setattr("ynoy.doctor.Database", unexpected_database)
    monkeypatch.setattr("ynoy.doctor._private_root_check", _ready_private_root)
    settings = _settings(
        tmp_path,
        "postgresql://user:secret@127.0.0.1:55432/ynoy",
    )

    result = run_doctor(settings, repository_root=Path(__file__).resolve().parents[1])

    checks = {check["name"]: check for check in result["checks"]}
    assert database_calls == 0
    assert checks["database_boundary"]["detail"] == "database_environment_options_blocked"
    assert checks["database_version"]["detail"] == "database_environment_options_blocked"
    assert checks["database_role"]["detail"] == "database_environment_options_blocked"
    assert result["synthetic_ready"] is False
    assert result["real_data_ready"] is False


def test_doctor_rejects_exact_versions_when_schema_is_not_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StaleSchemaDatabase:
        def __init__(self, _: str) -> None:
            pass

        def status(self) -> dict[str, object]:
            return {
                "postgres_version": "18.4",
                "pgvector_version": "0.8.2",
                "migration_current": False,
                "database_user_is_superuser": False,
                "audit_can_insert": True,
                "audit_can_update": False,
                "audit_can_delete": False,
                "audit_can_truncate": False,
            }

    for variable in LIBPQ_ENVIRONMENT_OVERRIDES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr("ynoy.doctor.Database", StaleSchemaDatabase)
    monkeypatch.setattr("ynoy.doctor._private_root_check", _ready_private_root)
    settings = _settings(
        tmp_path,
        "postgresql://user:secret@127.0.0.1:55432/ynoy",
    )

    result = run_doctor(settings, repository_root=Path(__file__).resolve().parents[1])
    checks = {check["name"]: check for check in result["checks"]}

    assert checks["database_version"]["status"] == "fail"
    assert checks["database_version"]["detail"]["migration_current"] is False
    assert result["synthetic_ready"] is False
    assert result["real_data_ready"] is False


def test_public_repository_failure_blocks_real_data_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ynoy.doctor._private_root_check", _ready_private_root)
    monkeypatch.setattr(
        "ynoy.doctor._repository_check",
        lambda _: {
            "name": "public_repository_boundary",
            "status": "fail",
            "detail": "private-looking tracked artifacts found",
        },
    )
    monkeypatch.setattr(
        "ynoy.doctor._database_boundary_check",
        lambda _: {"name": "database_boundary", "status": "pass", "detail": "local"},
    )
    monkeypatch.setattr(
        "ynoy.doctor._database_version_check",
        lambda _: {"name": "database_version", "status": "pass", "detail": "pinned"},
    )
    monkeypatch.setattr(
        "ynoy.doctor._database_role_check",
        lambda _: {"name": "database_role", "status": "pass", "detail": "restricted"},
    )

    result = run_doctor(
        _settings(tmp_path, "postgresql://user:secret@127.0.0.1:55432/ynoy"),
        repository_root=tmp_path,
    )

    assert result["synthetic_ready"] is True
    assert result["real_data_ready"] is False
    assert result["status"] == "synthetic_ready"
