from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest
from support.persona_pack import built_pack, pack_atoms

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.full_persona.responder import LocalPersonaResponder

MODEL = "ynoy-persona-fixture"
REVISION = "fixture-r1"
MODEL_SHA = "a" * 64


@contextmanager
def responder_server() -> Any:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(payload)
            body = json.dumps(model_response(sorted(_atom_ids(payload)))).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/v1/chat/completions", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def responder(
    *, attested: bool = True, endpoint: str = "http://127.0.0.1:18100/v1/chat/completions"
) -> LocalPersonaResponder:
    return LocalPersonaResponder(
        endpoint=endpoint,
        model=MODEL,
        revision=REVISION,
        artifact_sha256=MODEL_SHA,
        local_attested=attested,
    )


def model_response(
    used_atom_ids: list[str],
    *,
    model: str = MODEL,
    response_text: str = "Synthetic bounded response.",
    uncertainties: list[str] | None = None,
    should_abstain: bool = True,
) -> dict[str, object]:
    candidate = {
        "response_text": response_text,
        "used_atom_ids": used_atom_ids,
        "uncertainties": uncertainties or ["synthetic fixture; not calibrated"],
        "should_abstain": should_abstain,
    }
    return {
        "model": model,
        "choices": [{"message": {"content": json.dumps(candidate)}}],
    }


def _atom_ids(value: object) -> set[str]:
    if isinstance(value, str):
        try:
            return _atom_ids(json.loads(value))
        except json.JSONDecodeError:
            return set()
    found: set[str] = set()
    if isinstance(value, dict):
        atom_id = value.get("atom_id")
        if isinstance(atom_id, str):
            found.add(atom_id)
        for item in value.values():
            found.update(_atom_ids(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_atom_ids(item))
    return found


def _keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(str(key) for key in value)
        for item in value.values():
            found.update(_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_keys(item))
    return found


@pytest.mark.parametrize(
    ("endpoint", "attested", "sha", "error_type", "code"),
    [
        (
            "http://127.0.0.1:18100/v1/chat/completions",
            False,
            MODEL_SHA,
            PolicyViolation,
            "persona_responder_attestation_required",
        ),
        (
            "https://model.example.invalid/v1/chat/completions",
            True,
            MODEL_SHA,
            DataValidationError,
            "persona_responder_not_loopback",
        ),
        (
            "http://127.0.0.1:18100/v1/chat/completions",
            True,
            "bad",
            DataValidationError,
            "persona_responder_identity_invalid",
        ),
    ],
)
def test_responder_validates_attestation_loopback_and_identity_before_transport(
    endpoint: str,
    attested: bool,
    sha: str,
    error_type: type[Exception],
    code: str,
) -> None:
    with pytest.raises(error_type) as blocked:
        LocalPersonaResponder(
            endpoint=endpoint,
            model=MODEL,
            revision=REVISION,
            artifact_sha256=sha,
            local_attested=attested,
        )
    assert blocked.value.code == code  # type: ignore[attr-defined]


def test_structured_request_is_bounded_and_result_is_non_authoritative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    requests: list[dict[str, object]] = []

    def transport(_: str, payload: dict[str, object], **__: object) -> dict[str, object]:
        requests.append(payload)
        selected = sorted(_atom_ids(payload))[: pack.config.max_retrieval_hits]
        return model_response(selected)

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", transport)
    result = responder().respond(pack, "What should I do about Python?", arm="structured")

    assert len(requests) == 1
    payload = requests[0]
    selected = _atom_ids(payload)
    available = {atom.atom_id for atom in pack_atoms(pack)}
    assert selected <= available
    assert len(selected) <= pack.config.max_retrieval_hits
    assert {"target", "label", "focus"}.isdisjoint(_keys(payload))
    observations = json.loads(payload["messages"][1]["content"])["persona_observations"]
    assert all(item["source_role"] == "direct_user_expression" for item in observations)
    assert all("PLEASE IMPLEMENT THIS PLAN" not in item["claim"] for item in observations)
    dumped = result.model_dump(mode="json")
    assert dumped["judgment_basis"] == "abstention"
    assert dumped["calibration_status"] == "not_calibrated"
    assert dumped["authority"] == "none"
    assert dumped["action_status"] == "not_performed"
    assert dumped["send_enabled"] is False
    assert dumped["execute_enabled"] is False
    assert dumped["automatic_core"] is False
    assert dumped["target_seen"] is False
    assert set(dumped["used_atom_ids"]) <= selected
    assert isinstance(dumped["response_sha256"], str)
    assert isinstance(dumped["provenance_sha256"], str)


def test_generic_request_contains_no_personal_atoms_and_model_cannot_cite_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    calls: list[dict[str, object]] = []
    atom_id = pack_atoms(pack)[0].atom_id

    def transport(_: str, payload: dict[str, object], **__: object) -> dict[str, object]:
        calls.append(payload)
        return model_response([atom_id])

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", transport)
    with pytest.raises(AdapterError) as blocked:
        responder().respond(pack, "Give a generic answer.", arm="generic")
    assert blocked.value.code == "persona_responder_atom_ids_invalid"
    assert _atom_ids(calls[0]) == set()


def test_structured_responder_rejects_unknown_used_atom_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    unknown = "f" * 64
    monkeypatch.setattr(
        "ynoy.full_persona.responder.post_json",
        lambda *_args, **_kwargs: model_response([unknown]),
    )
    with pytest.raises(AdapterError) as blocked:
        responder().respond(pack, "What about Python?", arm="structured")
    assert blocked.value.code == "persona_responder_atom_ids_invalid"


def test_responder_rejects_oversized_query_before_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    calls = 0

    def unexpected(*_: object, **__: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("oversized responder input reached transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    with pytest.raises(DataValidationError) as blocked:
        responder().respond(pack, "x" * 100_000, arm="structured")
    assert blocked.value.code == "persona_responder_input_too_large"
    assert calls == 0


def test_responder_rejects_unsupported_arm_before_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    calls = 0

    def unexpected(*_: object, **__: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("unsupported arm reached transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    with pytest.raises(DataValidationError) as blocked:
        responder().respond(pack, "bounded query", arm="direct")  # type: ignore[arg-type]
    assert blocked.value.code == "persona_responder_arm_invalid"
    assert calls == 0


def test_responder_rejects_blank_query_before_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    calls = 0

    def unexpected(*_: object, **__: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("blank query reached transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    with pytest.raises(DataValidationError) as blocked:
        responder().respond(pack, " \t\n", arm="generic")
    assert blocked.value.code == "persona_responder_query_empty"
    assert calls == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.update({"model": "unexpected-model"}),
        lambda raw: raw["choices"][0]["message"].update({"content": "{}"}),
    ],
)
def test_responder_rejects_serving_model_or_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, mutate: Callable[[dict[str, object]], None]
) -> None:
    pack = built_pack(tmp_path)[3]
    raw = model_response([])
    mutate(raw)
    monkeypatch.setattr("ynoy.full_persona.responder.post_json", lambda *_args, **_kwargs: raw)
    with pytest.raises(AdapterError) as blocked:
        responder().respond(pack, "bounded query", arm="generic")
    assert blocked.value.code in {
        "persona_responder_identity_mismatch",
        "persona_responder_schema_invalid",
    }
