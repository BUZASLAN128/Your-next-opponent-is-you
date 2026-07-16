from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ynoy.config import Settings
from ynoy.database_policy import require_local_database
from ynoy.errors import YnoyError
from ynoy.policy import assess_private_root, is_loopback_url
from ynoy.repository_guard import looks_private, repository_check
from ynoy.storage import Database

Check = dict[str, object]


def run_doctor(settings: Settings, *, repository_root: Path) -> dict[str, object]:
    checks = [
        _python_check(),
        _repository_check(repository_root),
        _private_root_check(settings),
        _database_boundary_check(settings),
        _database_version_check(settings),
        _database_role_check(settings),
        _reasoner_check(settings),
        _embedding_check(settings),
    ]
    by_name = {str(check["name"]): check for check in checks}
    repository_ready = by_name["public_repository_boundary"]["status"] == "pass"
    database_ready = by_name["database_version"]["status"] == "pass"
    boundary_ready = by_name["database_boundary"]["status"] == "pass"
    role_ready = by_name["database_role"]["status"] == "pass"
    private_status = by_name["private_root"]
    synthetic_ready = bool(private_status.get("synthetic_ready")) and database_ready
    real_ready = (
        bool(private_status.get("real_data_ready"))
        and repository_ready
        and database_ready
        and boundary_ready
        and role_ready
    )
    return {
        "status": "real_data_ready"
        if real_ready
        else "synthetic_ready"
        if synthetic_ready
        else "blocked",
        "synthetic_ready": synthetic_ready,
        "real_data_ready": real_ready,
        "checks": checks,
    }


def _python_check() -> Check:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    passed = sys.version_info[:2] == (3, 12)
    return {
        "name": "python_version",
        "status": "pass" if passed else "fail",
        "detail": version,
        "expected": "3.12.x",
    }


def _repository_check(root: Path) -> Check:
    return repository_check(root)


def _looks_private(value: str) -> bool:
    return looks_private(value)


def _private_root_check(settings: Settings) -> Check:
    if settings.private_root is None:
        return {
            "name": "private_root",
            "status": "fail",
            "detail": "not_configured",
            "synthetic_ready": False,
            "real_data_ready": False,
        }
    assessment = assess_private_root(settings.private_root)
    return {
        "name": "private_root",
        "status": "pass" if assessment.synthetic_ready else "fail",
        "detail": "outside_git" if assessment.outside_git else "inside_git",
        "synthetic_ready": assessment.synthetic_ready,
        "real_data_ready": assessment.real_data_ready,
    }


def _database_boundary_check(settings: Settings) -> Check:
    if settings.database_url is None or settings.private_root is None:
        return {"name": "database_boundary", "status": "fail", "detail": "not_configured"}
    try:
        require_local_database(
            settings.database_url,
            private_root=settings.private_root,
            postgres_data_path=settings.postgres_data_path,
            real_data=True,
        )
    except YnoyError as exc:
        return {"name": "database_boundary", "status": "fail", "detail": exc.code}
    return {"name": "database_boundary", "status": "pass", "detail": "loopback_private_bind"}


def _database_version_check(settings: Settings) -> Check:
    if settings.database_url is None:
        return {"name": "database_version", "status": "fail", "detail": "not_configured"}
    transport_error = _database_transport_error(settings.database_url)
    if transport_error:
        return {"name": "database_version", "status": "fail", "detail": transport_error}
    try:
        status: dict[str, Any] = Database(settings.database_url).status()
    except YnoyError as exc:
        return {"name": "database_version", "status": "fail", "detail": exc.code}
    passed = (
        status.get("postgres_version") == "18.4"
        and status.get("pgvector_version") == "0.8.2"
        and status.get("migration_current") is True
    )
    return {
        "name": "database_version",
        "status": "pass" if passed else "fail",
        "detail": status,
    }


def _reasoner_check(settings: Settings) -> Check:
    configured = settings.local_reasoner_url is not None
    loopback = configured and is_loopback_url(settings.local_reasoner_url or "")
    trusted = loopback and settings.local_model_attested
    return {
        "name": "local_reasoner",
        "status": "pass" if trusted else "warn",
        "detail": (
            "trusted_local_attested"
            if trusted
            else "loopback_unattested"
            if loopback
            else "not_configured_or_not_loopback"
        ),
        "model": settings.local_reasoner_model,
        "transport_loopback": loopback,
        "provider_local_attested": settings.local_model_attested,
        "live_model_proof": False,
    }


def _database_role_check(settings: Settings) -> Check:
    if settings.database_url is None:
        return {"name": "database_role", "status": "fail", "detail": "not_configured"}
    transport_error = _database_transport_error(settings.database_url)
    if transport_error:
        return {"name": "database_role", "status": "fail", "detail": transport_error}
    try:
        status: dict[str, Any] = Database(settings.database_url).status()
    except YnoyError as exc:
        return {"name": "database_role", "status": "fail", "detail": exc.code}
    unsafe = bool(status.get("database_user_is_superuser")) or any(
        bool(status.get(name))
        for name in ("audit_can_update", "audit_can_delete", "audit_can_truncate")
    )
    can_append = bool(status.get("audit_can_insert"))
    passed = not unsafe and can_append
    return {
        "name": "database_role",
        "status": "pass" if passed else "fail",
        "detail": "restricted_runtime_role" if passed else "unsafe_audit_or_role_privileges",
        "database_user": status.get("database_user"),
    }


def _database_transport_error(database_url: str) -> str | None:
    try:
        require_local_database(
            database_url,
            private_root=Path.cwd(),
            postgres_data_path=None,
            real_data=False,
        )
    except YnoyError as exc:
        return exc.code
    return None


def _embedding_check(settings: Settings) -> Check:
    return {
        "name": "embedding_baseline",
        "status": "warn",
        "detail": "adapter_contract_only_no_live_model_proof",
        "model": settings.embedding_model,
    }
