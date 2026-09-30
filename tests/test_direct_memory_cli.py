from __future__ import annotations

import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest

from tests.direct_memory_fixtures import (
    CLAIM_ID,
    NOW,
    PROJECT,
    SOURCE_ID,
    SOURCE_TEXT,
    make_native_review,
)
from ynoy.cli import main
from ynoy.decision_brief import resolve_decision_brief
from ynoy.direct_memory.codec import decision_payload_sha256, strict_dumps
from ynoy.extractor import LocalAtomicExtractor
from ynoy.models import ConfirmClaimDecision, ScopeRef
from ynoy.models.review_state import ReviewedInteractionState
from ynoy.reasoner import LocalOpenAIReasoner
from ynoy.util import canonical_sha256, sha256_text


def _write(root: Path, name: str, value: object) -> str:
    path = root / f"{name}.json"
    path.write_text(strict_dumps(value), encoding="utf-8")
    return str(path)


def _cli(root: Path, capsys: pytest.CaptureFixture[str], *arguments: str, expected: int = 0):
    code = main(["--private-root", str(root), "direct-memory", "--synthetic", *arguments])
    output = json.loads(capsys.readouterr().out)
    assert code == expected, output
    assert output["ok"] == (expected == 0)
    return output.get("result", output.get("error"))


def _block_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("direct-memory CLI attempted a model, network or PostgreSQL call")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(LocalOpenAIReasoner, "complete", forbidden)
    monkeypatch.setattr(LocalAtomicExtractor, "propose", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)


def _propose(root: Path, capsys: pytest.CaptureFixture[str]):
    source = _write(
        root,
        "source",
        {
            "source_id": SOURCE_ID,
            "project": PROJECT,
            "said_at": NOW,
            "exact_text": SOURCE_TEXT,
        },
    )
    event = _cli(root, capsys, "live-input", source, "--expected-revision", "0")
    native = make_native_review()
    receipt = _write(root, "receipt", native.source.model_dump(mode="json"))
    claims = _write(
        root,
        "claims",
        [
            {
                "fact_key": "communication.concise",
                "evidence_ids": [SOURCE_ID],
                "proposal": native.claims[0].model_dump(mode="json"),
            }
        ],
    )
    review = _cli(
        root,
        capsys,
        "review",
        SOURCE_ID,
        "--receipt",
        receipt,
        "--claims",
        claims,
        "--expected-revision",
        "1",
    )
    assert review["review"]["proposal_method"] == "manual"
    assert not review["review"]["provider_used"]
    return event, review


def _confirm(root: Path, capsys: pytest.CaptureFixture[str], review: dict[str, object]):
    decisions = (ConfirmClaimDecision(claim_id=CLAIM_ID, subject_id="self"),)
    digest = decision_payload_sha256(decisions)
    live = _write(
        root,
        "current-correction",
        {
            "source_id": "live-confirm",
            "project": PROJECT,
            "said_at": NOW,
            "exact_text": "Confirm the stated preference.",
            "authorization_intent": {
                "action": "correct",
                "payload_sha256": digest,
                "subject_id": "self",
                "review_sha256": review["review_sha256"],
            },
        },
    )
    _cli(root, capsys, "live-input", live, "--expected-revision", "2")
    auth = _cli(
        root,
        capsys,
        "authorize",
        "live-confirm",
        "--action",
        "correct",
        "--payload-sha256",
        digest,
        "--review-sha256",
        str(review["review_sha256"]),
    )
    return _cli(
        root,
        capsys,
        "correct",
        str(review["review_id"]),
        "--decisions",
        _write(root, "decisions", [item.model_dump(mode="json") for item in decisions]),
        "--authorization",
        _write(root, "authorization", auth),
        "--expected-revision",
        "3",
    )


def test_actual_cli_persists_native_review_correction_reload_without_model_calls(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_calls(monkeypatch)
    event, review = _propose(tmp_path, capsys)
    correction = _confirm(tmp_path, capsys, review)
    assert (tmp_path / "direct-memory.sqlite3").is_file()
    assert _cli(tmp_path, capsys, "revision", PROJECT)["revision"] == 4
    source = _cli(tmp_path, capsys, "source", SOURCE_ID)
    assert source["exact_text"] == SOURCE_TEXT
    assert source["sha256"] == sha256_text(SOURCE_TEXT)
    assert source["recorded_at"] == event["recorded_at"]
    cutoff = datetime.now(UTC) + timedelta(days=1)
    brief = _cli(
        tmp_path,
        capsys,
        "brief",
        PROJECT,
        "--as-of",
        cutoff.isoformat(),
        "--known-at",
        cutoff.isoformat(),
    )
    state = ReviewedInteractionState.model_validate(correction["state"])
    native = resolve_decision_brief(state, ScopeRef(person_id="self", project=PROJECT), cutoff)
    assert brief["native_briefs"][0] == native.model_dump(mode="json")
    assert brief["native_brief_hashes"][0] == canonical_sha256(native.model_dump(mode="json"))
    assert not brief["automatic_core_promotion"] and brief["authority"] == "none"
    again = _cli(
        tmp_path,
        capsys,
        "brief",
        PROJECT,
        "--as-of",
        cutoff.isoformat(),
        "--known-at",
        cutoff.isoformat(),
    )
    assert again == brief
    export = tmp_path / "backup-evidence.jsonl"
    _cli(tmp_path, capsys, "export", "--project", PROJECT, "--output", str(export))
    records = [json.loads(line) for line in export.read_text(encoding="utf-8").splitlines()]
    assert any(row["record_type"] == "correction" for row in records)
    assert any(
        row["record_type"] == "source_event" and row["record"]["sha256"] == source["sha256"]
        for row in records
    )
    _cli(tmp_path, capsys, "backup", "--output", str(tmp_path / "snapshot.sqlite3"))


def test_prepared_index_actual_cli_roundtrip_returns_exact_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_calls(monkeypatch)
    bundle = _write(
        tmp_path,
        "prepared",
        {
            "name": "Synthetic guide",
            "pages": ["Exact page ✓", "Second exact page"],
            "tree": {
                "node_id": "root",
                "title": "Chapter",
                "start_index": 1,
                "end_index": 2,
                "summary": "Navigation only",
            },
        },
    )
    document = _cli(tmp_path, capsys, "import-document", bundle)
    document_id = document["document_id"]
    assert _cli(tmp_path, capsys, "list-documents")["documents"] == [document]
    assert _cli(tmp_path, capsys, "tree", document_id)["tree"]["summary"] == "Navigation only"
    nodes = _cli(tmp_path, capsys, "read-nodes", document_id, "root")["nodes"]
    pages = _cli(tmp_path, capsys, "read-pages", document_id, "1", "2")["pages"]
    assert nodes[0]["pages"] == pages
    assert pages[0]["text"] == "Exact page ✓"
    assert pages[0]["content_sha256"] == sha256_text("Exact page ✓")
    assert pages[0]["source_ref"] == f"{document_id}#page=1"
    assert not (tmp_path / "direct-memory.sqlite3").exists()


@pytest.mark.parametrize("extra", ["recorded_at", "authorization_intent", "source_type"])
def test_imported_source_cli_cannot_smuggle_live_authority_or_recorded_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: str
) -> None:
    payload = {
        "source_id": SOURCE_ID,
        "project": PROJECT,
        "speaker": "user",
        "said_at": NOW,
        "exact_text": SOURCE_TEXT,
        extra: "untrusted",
    }
    result = _cli(
        tmp_path,
        capsys,
        "source-event",
        _write(tmp_path, "import", payload),
        "--expected-revision",
        "0",
        expected=2,
    )
    assert result["code"] == "direct_memory_input_invalid"
    assert _cli(tmp_path, capsys, "revision", PROJECT)["revision"] == 0


def test_cli_refuses_naive_temporal_cutoff_and_existing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    error = _cli(
        tmp_path,
        capsys,
        "brief",
        PROJECT,
        "--as-of",
        "2026-09-30T12:00:00",
        "--known-at",
        NOW.isoformat(),
        expected=2,
    )
    assert error["code"] == "direct_memory_time_invalid"
    output = tmp_path / "existing.jsonl"
    output.write_text("Synthetic retained", encoding="utf-8")
    result = _cli(tmp_path, capsys, "export", "--output", str(output), expected=2)
    assert result["code"] == "direct_memory_output_exists"
    assert output.read_text(encoding="utf-8") == "Synthetic retained"
