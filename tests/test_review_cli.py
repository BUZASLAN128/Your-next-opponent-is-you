from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

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
_RESPONSE = "Use a local extractor and keep automatic promotion disabled."


def _known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _interaction() -> InteractionReceipt:
    prompt = "Select a synthetic local extractor."
    return InteractionReceipt(
        record_id=UUID(int=1),
        created_at=_NOW,
        source_name="synthetic-review-cli",
        conversation_id="synthetic-conversation",
        turn_id="synthetic-turn",
        event_time=_NOW,
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator="fixture://review-cli/prompt",
            speaker=Speaker.ASSISTANT,
            text=_known(prompt),
            content_sha256=sha256_text(prompt),
        ),
        response=_RESPONSE,
        response_sha256=sha256_text(_RESPONSE),
        subject_id="self",
        scope=ScopeRef(person_id="self", project="synthetic-pilot"),
        question_resolved=_known("Try one proposal-only local extractor."),
        source_data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )


def _model_claim(
    source_text: str, literal: str, target_layer: str, claim_type: str
) -> dict[str, object]:
    return {
        "source_text": source_text,
        "occurrence": 1,
        "literal_normalization": literal,
        "inference": None,
        "candidate_consequence": None,
        "speech_act": "requirement",
        "modality": "must",
        "claim_type": claim_type,
        "target_layer": target_layer,
        "classification_confidence": "medium",
        "applicability_confidence": "unknown",
    }


def _model_response() -> dict[str, object]:
    claims = [
        _model_claim(
            _RESPONSE,
            "Use a local extractor.",
            "architecture_candidate",
            "requirement",
        ),
        _model_claim(
            _RESPONSE,
            "Keep automatic promotion disabled.",
            "protected_control",
            "guardrail",
        ),
    ]
    return {"choices": [{"message": {"content": json.dumps({"claims": claims})}}]}


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


def _configure_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNOY_LOCAL_REASONER_URL", "http://127.0.0.1:18100/v1/chat/completions")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_MODEL", "ynoy-extractor-qwen3-8b-q4km")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_REVISION", "7c41481f57cb95916b40956ab2f0b139b296d974")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_ARTIFACT_SHA256", _MODEL_SHA)
    monkeypatch.setenv("YNOY_LOCAL_MODEL_ATTESTED", "true")
    monkeypatch.delenv("YNOY_DATABASE_URL", raising=False)


def _propose_first_claim(
    prefix: list[str], source: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[str, object]:
    code, proposed = _run_cli([*prefix, "review", "propose", str(source), "--synthetic"], capsys)
    assert code == 0 and proposed["ok"] is True
    result = proposed["result"]
    assert isinstance(result, dict)
    review_path = str(result["review_path"])
    assert result["claim_count"] == 2 and result["provider_used"] is True
    code, batched = _run_cli(
        [*prefix, "review", "batch", review_path, "--limit", "1", "--synthetic"], capsys
    )
    batch = batched["result"]
    assert code == 0 and isinstance(batch, dict)
    assert batch["returned"] == 1 and batch["has_more"] is True
    claims = batch["claims"]
    assert isinstance(claims, list) and isinstance(claims[0], dict)
    return review_path, claims[0]["record_id"]


def _apply_first_claim(
    tmp_path: Path,
    prefix: list[str],
    review_path: str,
    claim_id: object,
    capsys: pytest.CaptureFixture[str],
) -> str:
    decisions = _write_json(
        tmp_path / "first-decisions.json",
        [{"claim_id": claim_id, "subject_id": "self", "action": "confirm"}],
    )
    code, partial = _run_cli(
        [*prefix, "review", "apply", review_path, str(decisions), "--synthetic"], capsys
    )
    result = partial["result"]
    assert code == 0 and isinstance(result, dict) and result["pending_count"] == 1
    return str(result["receipt_path"])


def _apply_second_claim(
    tmp_path: Path,
    prefix: list[str],
    review_path: str,
    first_receipt: str,
    capsys: pytest.CaptureFixture[str],
) -> str:
    code, batch = _run_cli(
        [*prefix, "review", "batch", review_path, "--start", "2", "--synthetic"], capsys
    )
    result = batch["result"]
    assert code == 0 and isinstance(result, dict)
    claims = result["claims"]
    assert isinstance(claims, list) and isinstance(claims[0], dict)
    decisions = _write_json(
        tmp_path / "second-decisions.json",
        [
            {
                "claim_id": claims[0]["record_id"],
                "subject_id": "self",
                "action": "reject",
                "reason": "Synthetic rejection.",
            }
        ],
    )
    code, complete = _run_cli(
        [
            *prefix,
            "review",
            "apply",
            review_path,
            str(decisions),
            "--receipt",
            first_receipt,
            "--synthetic",
        ],
        capsys,
    )
    complete_result = complete["result"]
    assert code == 0 and isinstance(complete_result, dict)
    assert complete_result["status"] == "reviewed" and complete_result["pending_count"] == 0
    return str(complete_result["receipt_path"])


def _assert_replay(
    prefix: list[str],
    review_path: str,
    receipts: tuple[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [*prefix, "review", "replay", review_path]
    for receipt in receipts:
        arguments.extend(("--receipt", receipt))
    code, replayed = _run_cli([*arguments, "--synthetic"], capsys)
    result = replayed["result"]
    assert code == 0 and isinstance(result, dict)
    assert result["deterministic"] is True and result["receipt_count"] == 2


def test_review_cli_proposes_batches_corrects_and_replays_without_database(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_model(monkeypatch)
    calls: list[object] = []

    def transport(_: str, payload: object, **__: object) -> object:
        calls.append(payload)
        return _model_response()

    monkeypatch.setattr("ynoy.extractor.post_json", transport)
    root = tmp_path / "private"
    source = _write_json(tmp_path / "interaction.json", _interaction().model_dump(mode="json"))
    prefix = ["--private-root", str(root)]
    review_path, first_id = _propose_first_claim(prefix, source, capsys)
    first_receipt = _apply_first_claim(tmp_path, prefix, review_path, first_id, capsys)
    second_receipt = _apply_second_claim(tmp_path, prefix, review_path, first_receipt, capsys)
    _assert_replay(prefix, review_path, (first_receipt, second_receipt), capsys)
    assert calls and len(calls) == 1


def test_real_review_source_inside_git_is_rejected_before_model_transport(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_model(monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(
        "ynoy.extractor.post_json", lambda *_args, **_kwargs: calls.append("called")
    )

    code, payload = _run_cli(["review", "propose", __file__], capsys)

    assert code == 2 and payload["ok"] is False
    error = payload["error"]
    assert isinstance(error, dict) and error["code"] == "private_root_inside_git"
    assert calls == []
