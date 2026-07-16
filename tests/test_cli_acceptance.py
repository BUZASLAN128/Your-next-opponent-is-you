from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import benchmark_cases

from ynoy.util import sha256_file

pytestmark = [pytest.mark.integration, pytest.mark.acceptance]


def _run_cli(private_root: Path, database_url: str, *arguments: str) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "ynoy",
        "--private-root",
        str(private_root),
        "--database-url",
        database_url,
        "--indent",
        "0",
        *arguments,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
    try:
        payload: dict[str, Any] = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"CLI emitted invalid JSON (exit={completed.returncode}): {completed.stdout!r}"
        ) from exc
    assert completed.returncode == 0, payload
    assert payload["ok"] is True
    return payload["result"]


def _prepare_bootstrap(tmp_path: Path) -> Path:
    source = tmp_path / "bootstrap-fixture.json"
    source.write_text(
        json.dumps(
            [
                {
                    "statement": "Reject hidden tenant fallback. decision:reject",
                    "synthetic": True,
                    "scope": {"project": "pilot"},
                }
            ]
        ),
        encoding="utf-8",
    )
    return source


def _prepare_cases(tmp_path: Path) -> Path:
    source = tmp_path / "benchmark-cases.json"
    source.write_text(
        json.dumps([case.model_dump(mode="json") for case in benchmark_cases()]),
        encoding="utf-8",
    )
    return source


def _run_corpus_workflow(
    root: Path, database_url: str, archive: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    inventory = _run_cli(root, database_url, "corpus", "inventory", str(archive), "--synthetic")
    approval = _run_cli(
        root,
        database_url,
        "corpus",
        "approve",
        inventory["manifest_id"],
        "--synthetic",
        "--operations",
        "ingest",
    )
    ingestion = _run_cli(
        root,
        database_url,
        "corpus",
        "ingest",
        str(archive),
        inventory["manifest_id"],
        approval["approval_id"],
        "--synthetic",
    )
    return inventory, ingestion


def _run_benchmark_workflow(
    root: Path, database_url: str, cases: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    frozen = _run_cli(
        root,
        database_url,
        "benchmark",
        "freeze",
        str(cases),
        "--name",
        "synthetic-cli-pilot",
        "--development-fraction",
        "0.5",
    )
    run = _run_cli(root, database_url, "benchmark", "run", frozen["manifest_id"])
    report = _run_cli(
        root,
        database_url,
        "benchmark",
        "report",
        frozen["manifest_id"],
        run["run_id"],
    )
    return frozen, run, report


def test_synthetic_cli_end_to_end(tmp_path: Path, make_chatgpt_zip, test_database_url: str) -> None:
    root = tmp_path / "private-artifacts"
    archive = make_chatgpt_zip()
    _run_cli(root, test_database_url, "database", "migrate")
    inventory, ingestion = _run_corpus_workflow(root, test_database_url, archive)
    assert inventory["claims_derived"] == 0
    assert ingestion["normalized_events"] == 3
    bootstrap = _run_cli(
        root,
        test_database_url,
        "bootstrap",
        "import",
        str(_prepare_bootstrap(tmp_path)),
        "--synthetic",
    )
    assert bootstrap["automatic_core_promotion"] is False
    mirror = _run_cli(
        root,
        test_database_url,
        "mirror",
        "predict",
        "--task",
        "tenant fallback",
        "--project",
        "pilot",
        "--reasoner",
        "deterministic",
        "--synthetic",
    )
    assert mirror["authority"] == "none" and mirror["personal_fit"] == "known"
    assert mirror["proposed_action"] is None and mirror["action_receipt"] is None
    assert mirror["action_status"] == "not_performed"
    assert mirror["answer_kind"] == "untrusted_reasoner_advisory"
    _, run, report = _run_benchmark_workflow(root, test_database_url, _prepare_cases(tmp_path))
    assert run["status"] == "complete" and run["acceptance_status"] == "not_calibrated"
    assert report["local_only"] is True and Path(report["report_path"]).is_file()
    inspected = _run_cli(root, test_database_url, "memory", "inspect", "--synthetic")
    assert inspected["automatic_core_promotion"] is False
    plan = _run_cli(root, test_database_url, "erase", "plan", sha256_file(archive), "--synthetic")
    erased = _run_cli(
        root,
        test_database_url,
        "erase",
        "confirm",
        plan["plan_id"],
        plan["plan_sha256"],
        "--synthetic",
    )
    assert erased["local_deleted"] is True
    assert erased["provider_residual"] == "not_applicable_no_external_egress"
