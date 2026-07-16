from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from ynoy.models import AuditReceipt, BenchmarkCase, DecisionLabel
from ynoy.storage import Database


def synthetic_conversation() -> dict[str, object]:
    return {
        "id": "synthetic-conversation-1",
        "mapping": {
            "user-root": _node(
                "user-root",
                None,
                ["assistant-main", "assistant-branch"],
                "user",
                "Reject changes that weaken tenant isolation.",
                1_700_000_000,
            ),
            "assistant-main": _node(
                "assistant-main",
                "user-root",
                [],
                "assistant",
                "The user always accepts broad fallbacks.",
                1_700_000_001,
            ),
            "assistant-branch": _node(
                "assistant-branch",
                "user-root",
                [],
                "assistant",
                "Alternative assistant response.",
                1_700_000_002,
            ),
        },
    }


def _node(
    node_id: str,
    parent: str | None,
    children: list[str],
    role: str,
    text: str,
    created: int,
) -> dict[str, object]:
    return {
        "id": node_id,
        "parent": parent,
        "children": children,
        "message": {
            "author": {"role": role},
            "create_time": created,
            "content": {"content_type": "text", "parts": [text]},
        },
    }


@pytest.fixture
def make_chatgpt_zip(tmp_path: Path) -> Callable[..., Path]:
    def make(
        *,
        conversations: list[dict[str, object]] | None = None,
        marker: bool = True,
        member_name: str = "conversations.json",
        compression: int = ZIP_DEFLATED,
        extra_info: ZipInfo | None = None,
        extra_content: bytes = b"x",
    ) -> Path:
        path = tmp_path / f"fixture-{len(list(tmp_path.iterdir()))}.zip"
        with ZipFile(path, "w", compression=compression) as archive:
            archive.writestr(
                member_name,
                json.dumps(conversations or [synthetic_conversation()]),
            )
            if marker:
                archive.writestr(
                    "ynoy-synthetic-fixture.json",
                    json.dumps({"schema_version": "1.0", "synthetic": True}),
                )
            if extra_info is not None:
                archive.writestr(extra_info, extra_content)
        return path

    return make


def benchmark_cases() -> list[BenchmarkCase]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    hidden_labels = [
        DecisionLabel.ACCEPT,
        DecisionLabel.REJECT,
        DecisionLabel.CORRECT,
        DecisionLabel.DEFER,
    ]
    support_labels = [
        (DecisionLabel.REJECT, DecisionLabel.CORRECT, DecisionLabel.DEFER),
        (DecisionLabel.CORRECT, DecisionLabel.DEFER, DecisionLabel.ACCEPT),
        (DecisionLabel.DEFER, DecisionLabel.ACCEPT, DecisionLabel.REJECT),
        (DecisionLabel.ACCEPT, DecisionLabel.REJECT, DecisionLabel.CORRECT),
    ]
    return [
        BenchmarkCase(
            case_id=f"case-{index}",
            task_type="review",
            decision_class="change_decision",
            event_time=start + timedelta(days=index),
            dependency_cluster_id=f"cluster-{index}",
            task_context=f"Review tenant boundary change {index}",
            evidence=(f"observed tenant support decision:{support[0].value}",),
            declared_profile=(f"declared review support decision:{support[1].value}",),
            structured_core=(f"structured support decision:{support[2].value}",),
            hidden_target=hidden_label,
        )
        for index, (hidden_label, support) in enumerate(
            zip(hidden_labels, support_labels, strict=True)
        )
    ]


def synthetic_audit(
    *,
    event_type: str = "derive",
    reason_code: str = "pytest_synthetic_atomic_mutation",
    artifact_id: str | None = None,
) -> AuditReceipt:
    return AuditReceipt.model_validate(
        {
            "event_type": event_type,
            "actor_class": "pytest",
            "config_version": "1.0",
            "input_count": 0,
            "data_classes": ("D0",),
            "decision": "complete",
            "reason_code": reason_code,
            "artifact_id": artifact_id,
            "status": "success",
        }
    )


@pytest.fixture
def test_database_url() -> str:
    database_url = os.environ.get("YNOY_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("YNOY_TEST_DATABASE_URL is not configured")
    try:
        _validate_test_database_url(database_url)
    except ValueError as exc:
        pytest.fail(str(exc), pytrace=False)
    return database_url


@pytest.fixture
def test_database(test_database_url: str) -> Database:
    database = Database(test_database_url)
    database.migrate()
    return database


def _validate_test_database_url(database_url: str) -> None:
    message = (
        "YNOY_TEST_DATABASE_URL must use postgres/postgresql on a loopback host "
        "and database ynoy_test."
    )
    try:
        parsed = urlparse(database_url)
        host = (parsed.hostname or "").casefold()
        database_name = unquote(parsed.path.removeprefix("/"))
        query = parse_qs(parsed.query, keep_blank_values=True)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(message) from exc
    dangerous_overrides = {"host", "hostaddr", "dbname", "service", "servicefile"}
    valid = (
        parsed.scheme in {"postgres", "postgresql"}
        and host in {"127.0.0.1", "localhost", "::1"}
        and database_name == "ynoy_test"
        and not parsed.fragment
        and not dangerous_overrides.intersection(key.casefold() for key in query)
    )
    if not valid:
        raise ValueError(message)
