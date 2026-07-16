from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote, urlparse

from ynoy.errors import PolicyViolation

LIBPQ_ENVIRONMENT_OVERRIDES = frozenset(
    {
        "PGCHANNELBINDING",
        "PGCONNECT_TIMEOUT",
        "PGDATABASE",
        "PGGSSENCMODE",
        "PGHOST",
        "PGHOSTADDR",
        "PGLOADBALANCEHOSTS",
        "PGOPTIONS",
        "PGPASSFILE",
        "PGPASSWORD",
        "PGPORT",
        "PGREQUIREAUTH",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSSLCERT",
        "PGSSLCRL",
        "PGSSLCRLDIR",
        "PGSSLKEY",
        "PGSSLMODE",
        "PGSSLROOTCERT",
        "PGTARGETSESSIONATTRS",
        "PGUSER",
    }
)


def validated_loopback_hostaddr(database_url: str) -> str:
    try:
        parsed = urlparse(database_url)
        host = (parsed.hostname or "").casefold()
        _ = parsed.port
        username = parsed.username
        password = parsed.password
    except ValueError as exc:
        raise PolicyViolation(
            "database_url_invalid", "The PostgreSQL database URL is invalid."
        ) from exc
    valid_scheme = parsed.scheme in {"postgres", "postgresql"}
    if not valid_scheme or host not in {"127.0.0.1", "localhost", "::1"}:
        raise PolicyViolation(
            "database_not_loopback",
            "V1 database connections must use PostgreSQL on a loopback address.",
        )
    if parsed.params or parsed.query or parsed.fragment:
        raise PolicyViolation(
            "database_connection_options_blocked",
            "V1 database URLs must not use parameters, query options, or fragments.",
        )
    database_name = unquote(parsed.path.removeprefix("/"))
    if not username or not password or not database_name or "/" in database_name:
        raise PolicyViolation(
            "database_url_incomplete",
            "The database URL must contain explicit credentials and one database name.",
        )
    return "::1" if host == "::1" else "127.0.0.1"


def require_no_libpq_environment(
    environment: Mapping[str, str] | None = None,
) -> None:
    selected = os.environ if environment is None else environment
    blocked = sorted(name for name in LIBPQ_ENVIRONMENT_OVERRIDES if selected.get(name, "").strip())
    if blocked:
        raise PolicyViolation(
            "database_environment_options_blocked",
            "Unset libpq connection environment overrides before running YNOY.",
            details={"variables": blocked},
        )


def require_local_database(
    database_url: str,
    *,
    private_root: Path,
    postgres_data_path: Path | None,
    real_data: bool,
) -> str:
    hostaddr = validated_loopback_hostaddr(database_url)
    require_no_libpq_environment()
    if not real_data:
        return hostaddr
    if postgres_data_path is None:
        return hostaddr
    data_path = postgres_data_path.resolve()
    root = private_root.resolve()
    if data_path != root and root not in data_path.parents:
        raise PolicyViolation(
            "postgres_private_path_outside_root",
            "Configured PostgreSQL data must stay inside the explicit private root.",
        )
    return hostaddr
