from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ynoy.cli.context import CommandContext
from ynoy.cli.main import main
from ynoy.models import (
    DataClass,
    InteractionPrompt,
    InteractionReceipt,
    NullableReviewText,
    ScopeRef,
    Speaker,
)
from ynoy.util import sha256_text

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
_MODEL_SHA = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
_RESPONSE = "Keep this review local and require explicit user decisions."


def _known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _interaction() -> InteractionReceipt:
    return InteractionReceipt(
        record_id=UUID(int=10),
        created_at=_NOW,
        source_name="private-review-path",
        conversation_id="private-conversation",
        turn_id="private-turn",
        event_time=_NOW,
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator="local://private-review/prompt",
            speaker=Speaker.ASSISTANT,
            text=_known("Choose the local review boundary."),
            content_sha256=sha256_text("Choose the local review boundary."),
        ),
        response=_RESPONSE,
        response_sha256=sha256_text(_RESPONSE),
        subject_id="self",
        scope=ScopeRef(person_id="self", project="private-pilot"),
        question_resolved=_known("Use explicit local review decisions."),
        source_data_class=DataClass.RAW_CORPUS,
        synthetic=False,
    )


def _model_response() -> dict[str, object]:
    claim = {
        "source_text": _RESPONSE,
        "occurrence": 1,
        "literal_normalization": "Require explicit user decisions.",
        "inference": None,
        "candidate_consequence": None,
        "speech_act": "requirement",
        "modality": "must",
        "claim_type": "guardrail",
        "target_layer": "protected_control",
        "classification_confidence": "high",
        "applicability_confidence": "medium",
    }
    return {"choices": [{"message": {"content": json.dumps({"claims": [claim]})}}]}


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNOY_LOCAL_REASONER_URL", "http://127.0.0.1:18100/v1/chat/completions")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_MODEL", "ynoy-extractor-qwen3-8b-q4km")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_REVISION", "test-revision")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_ARTIFACT_SHA256", _MODEL_SHA)
    monkeypatch.setenv("YNOY_LOCAL_MODEL_ATTESTED", "true")
    monkeypatch.delenv("YNOY_DATABASE_URL", raising=False)


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _run_cli(
    arguments: Sequence[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return code, payload


def _propose_real_review(
    root: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str]:
    _configure(monkeypatch)
    monkeypatch.setattr("ynoy.extractor.post_json", lambda *_args, **_kwargs: _model_response())
    source = _write_json(root / "interaction.json", _interaction().model_dump(mode="json"))
    prefix = ["--private-root", str(root), "review"]
    code, payload = _run_cli([*prefix, "propose", str(source)], capsys)
    result = payload["result"]
    assert code == 0 and isinstance(result, dict)
    assert result["database_used"] is False and result["automatic_core_promotion"] is False
    review_path = str(result["review_path"])
    code, batch_payload = _run_cli([*prefix, "batch", review_path], capsys)
    batch = batch_payload["result"]
    assert code == 0 and isinstance(batch, dict)
    claims = batch["claims"]
    assert isinstance(claims, list) and isinstance(claims[0], dict)
    return review_path, str(claims[0]["record_id"])


def test_real_review_lifecycle_stays_inside_explicit_private_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private"
    review_path, claim_id = _propose_real_review(root, capsys, monkeypatch)
    decisions = _write_json(
        root / "decisions.json",
        [{"claim_id": claim_id, "subject_id": "self", "action": "confirm"}],
    )
    monkeypatch.setattr(
        CommandContext,
        "database",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("database called")),
    )
    prefix = ["--private-root", str(root), "review"]
    code, applied = _run_cli([*prefix, "apply", review_path, str(decisions)], capsys)
    result = applied["result"]
    assert code == 0 and isinstance(result, dict) and result["pending_count"] == 0
    assert result["database_used"] is False
    assert Path(str(result["receipt_path"])).is_relative_to(root)
    code, replayed = _run_cli(
        [*prefix, "replay", review_path, "--receipt", str(result["receipt_path"])], capsys
    )
    replay = replayed["result"]
    assert code == 0 and isinstance(replay, dict)
    assert replay["deterministic"] is True and replay["receipt_count"] == 1


def test_real_review_rejects_source_outside_selected_root_before_provider(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private"
    root.mkdir()
    source = _write_json(tmp_path / "outside.json", _interaction().model_dump(mode="json"))
    calls: list[str] = []
    _configure(monkeypatch)
    monkeypatch.setattr(
        "ynoy.extractor.post_json", lambda *_args, **_kwargs: calls.append("called")
    )

    code, payload = _run_cli(
        ["--private-root", str(root), "review", "propose", str(source)], capsys
    )

    assert code == 2 and payload["error"]["code"] == "private_source_outside_root"
    assert calls == []


def test_git_source_is_rejected_before_provider_or_artifact_work(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _configure(monkeypatch)
    monkeypatch.setattr(
        "ynoy.extractor.post_json", lambda *_args, **_kwargs: calls.append("called")
    )
    monkeypatch.setattr(
        CommandContext,
        "review_artifacts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("artifact store called")),
    )

    code, payload = _run_cli(["review", "propose", __file__], capsys)

    assert code == 2 and payload["error"]["code"] == "private_root_inside_git"
    assert calls == []
