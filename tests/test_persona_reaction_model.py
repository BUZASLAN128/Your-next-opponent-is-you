from __future__ import annotations

import json

import pytest
from test_persona_reaction_benchmark import _split

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.full_persona.reaction_model import (
    LocalReactionModelAdapter,
    parse_reaction_response,
)
from ynoy.util import canonical_sha256, sha256_text

_MODEL = "ynoy-test-local-8b"
_REVISION = "synthetic-revision-1"
_ARTIFACT = "a" * 64


def _adapter(**updates: object) -> LocalReactionModelAdapter:
    values: dict[str, object] = {
        "endpoint": "http://127.0.0.1:18100/v1/chat/completions",
        "model": _MODEL,
        "revision": _REVISION,
        "artifact_sha256": _ARTIFACT,
        "local_attested": True,
    }
    values.update(updates)
    return LocalReactionModelAdapter(**values)


@pytest.mark.parametrize(
    "updates, error",
    (
        ({"endpoint": "https://example.invalid/v1"}, DataValidationError),
        ({"local_attested": False}, PolicyViolation),
        ({"model": ""}, DataValidationError),
        ({"revision": ""}, DataValidationError),
        ({"artifact_sha256": "0" * 63}, DataValidationError),
    ),
)
def test_loopback_attestation_and_pinned_identity_fail_before_transport(
    updates: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        _adapter(**updates)


def _capture_requests(
    monkeypatch: pytest.MonkeyPatch,
    response: dict[str, object],
    *,
    structured_evidence_id: str | None = None,
):
    calls: list[dict[str, object]] = []

    def fake_post(endpoint: str, payload: dict[str, object], **_: object) -> dict[str, object]:
        assert endpoint.startswith("http://127.0.0.1:")
        calls.append(payload)
        candidate = dict(response)
        messages = payload.get("messages")
        user_packet = messages[-1] if isinstance(messages, list) else {}
        encoded = user_packet.get("content") if isinstance(user_packet, dict) else ""
        packet = json.loads(encoded) if isinstance(encoded, str) else {}
        if packet.get("arm") == "structured_persona" and structured_evidence_id:
            supplied = [
                item.get("evidence_id")
                for item in packet.get("history", [])
                if isinstance(item, dict) and item.get("evidence_id")
            ]
            candidate["evidence_ids"] = [
                structured_evidence_id if structured_evidence_id in supplied else supplied[0]
            ]
        return {
            "model": _MODEL,
            "choices": [{"message": {"content": json.dumps(candidate)}}],
        }

    monkeypatch.setattr("ynoy.full_persona.reaction_model.post_json", fake_post)
    return calls


def _decoded_user_packet(payload: dict[str, object]) -> dict[str, object]:
    messages = payload["messages"]
    assert isinstance(messages, list)
    user = messages[-1]
    assert isinstance(user, dict)
    return json.loads(user["content"])


def test_generic_request_contains_only_case_context(monkeypatch: pytest.MonkeyPatch) -> None:
    split = _split()
    calls = _capture_requests(
        monkeypatch,
        {"predicted_label": "decision", "ranking_score": 0.5, "evidence_ids": []},
        structured_evidence_id=split.history[0].evidence_id,
    )
    _adapter().predict_arm(split.manifest, (), split.cases, arm="generic_local_8b")
    packet = _decoded_user_packet(calls[0])
    assert packet["arm"] == "generic_local_8b"
    assert packet["context"]
    assert packet.get("history", []) == []
    encoded = json.dumps(packet, ensure_ascii=False)
    for forbidden in ("target", "locator", "manifest_sha256", "seal_sha256"):
        assert forbidden not in encoded.casefold()


def test_structured_request_is_bounded_development_only(monkeypatch: pytest.MonkeyPatch) -> None:
    split = _split()
    calls = _capture_requests(
        monkeypatch,
        {"predicted_label": "decision", "ranking_score": 0.5, "evidence_ids": []},
        structured_evidence_id=split.history[0].evidence_id,
    )
    _adapter().predict_arm(
        split.manifest,
        split.history,
        split.cases,
        arm="structured_persona",
    )
    packet = _decoded_user_packet(calls[0])
    encoded = json.dumps(packet, ensure_ascii=False)
    assert packet["history"]
    assert len(encoded) <= 8 * 1024
    sealed_ids = set(split.manifest.sealed_case_ids)
    assert not sealed_ids & set(encoded.split('"'))
    assert split.manifest.manifest_sha256 not in encoded
    assert split.target_seal.seal_sha256 not in encoded


def test_generic_and_structured_keep_identical_decode_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    split = _split()
    calls = _capture_requests(
        monkeypatch,
        {"predicted_label": "decision", "ranking_score": 0.5, "evidence_ids": []},
        structured_evidence_id=split.history[0].evidence_id,
    )
    adapter = _adapter()
    adapter.predict_arm(split.manifest, (), split.cases, arm="generic_local_8b")
    adapter.predict_arm(split.manifest, split.history, split.cases, arm="structured_persona")
    assert calls[0]["temperature"] == calls[-1]["temperature"] == 0
    assert calls[0]["max_tokens"] == calls[-1]["max_tokens"] == 384
    assert calls[0]["model"] == calls[-1]["model"] == _MODEL
    assert "response_format" not in calls[0] and "response_format" not in calls[-1]
    assert calls[0]["grammar"] != calls[-1]["grammar"]


def test_structured_non_abstention_requires_development_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    split = _split()
    _capture_requests(
        monkeypatch,
        {"predicted_label": "decision", "ranking_score": 0.5, "evidence_ids": []},
    )
    with pytest.raises((AdapterError, DataValidationError, ValueError)):
        _adapter().predict_arm(
            split.manifest,
            split.history,
            split.cases,
            arm="structured_persona",
        )


def test_rehashed_history_content_or_signal_fails_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    split = _split()
    calls = _capture_requests(
        monkeypatch,
        {"predicted_label": "abstain", "ranking_score": 0.0, "evidence_ids": []},
    )
    history = list(split.history)
    item = history[0]
    replacement = "correction" if item.observed_signal != "correction" else "decision"
    text = "rehashed history context"
    context = item.context[0].model_copy(
        update={"content": text, "content_sha256": sha256_text(text)}
    )
    payload = item.model_dump(mode="json", exclude={"history_sha256"})
    payload["context"] = [context.model_dump(mode="json")]
    payload["observed_signal"] = replacement
    history[0] = type(item).model_validate({**payload, "history_sha256": canonical_sha256(payload)})
    assert history[0].history_id == item.history_id
    with pytest.raises(DataValidationError):
        _adapter().predict_arm(
            split.manifest, tuple(history), split.cases, arm="structured_persona"
        )
    assert calls == []


def test_rehashed_case_context_fails_before_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    split = _split()
    calls = _capture_requests(
        monkeypatch,
        {"predicted_label": "abstain", "ranking_score": 0.0, "evidence_ids": []},
    )
    item = split.cases[0]
    text = "rehashed case context"
    context = item.context[0].model_copy(
        update={"content": text, "content_sha256": sha256_text(text)}
    )
    payload = item.model_dump(mode="json", exclude={"case_sha256"})
    payload["context"] = [context.model_dump(mode="json")]
    changed = type(item).model_validate({**payload, "case_sha256": canonical_sha256(payload)})
    assert changed.case_id == item.case_id
    cases = (changed, *split.cases[1:])
    with pytest.raises(DataValidationError):
        _adapter().predict_arm(split.manifest, (), cases, arm="generic_local_8b")
    assert calls == []


def test_model_envelope_identity_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    split = _split()

    def wrong_model(*_: object, **__: object) -> dict[str, object]:
        return {
            "model": "different-model",
            "choices": [{"message": {"content": json.dumps({"predicted_label": "decision"})}}],
        }

    monkeypatch.setattr("ynoy.full_persona.reaction_model.post_json", wrong_model)
    with pytest.raises((AdapterError, DataValidationError)):
        _adapter().predict_arm(split.manifest, (), split.cases, arm="generic_local_8b")


@pytest.mark.parametrize(
    "response",
    (
        {"predicted_label": "made_up", "ranking_score": 0.5, "evidence_ids": []},
        {"predicted_label": "decision", "ranking_score": 2, "evidence_ids": []},
        {"predicted_label": "decision", "ranking_score": 0.5, "evidence_ids": ["0"]},
        {"predicted_label": "decision", "ranking_score": 0.5, "evidence_ids": ["sealed"]},
    ),
)
def test_invalid_model_schema_label_or_citation_fails_closed(response: dict[str, object]) -> None:
    with pytest.raises((AdapterError, DataValidationError, ValueError)):
        parse_reaction_response(response, allowed_evidence_ids={"e" * 64})
