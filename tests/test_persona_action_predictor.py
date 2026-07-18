from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from test_persona_action_pilot import _prepared_pilot

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.persona_study.action_pilot_run import run_private_action_pilot
from ynoy.persona_study.action_predictor import LocalActionPredictor
from ynoy.persona_study.artifacts import PersonaStudyStore

ACTION_MODEL_SHA = "a" * 64


@contextmanager
def action_server(
    *, model: str = "fixture-model", signal: str = "evidence_demand"
) -> Iterator[tuple[str, list[dict[str, object]]]]:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            size = int(self.headers.get("Content-Length", "0"))
            requests.append(json.loads(self.rfile.read(size)))
            content = json.dumps({"predicted_signal": signal, "ranking_score": 0.5})
            body = json.dumps(
                {"model": model, "choices": [{"message": {"content": content}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

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


def _predictor(endpoint: str, *, attested: bool = True) -> LocalActionPredictor:
    return LocalActionPredictor(
        endpoint=endpoint,
        model="fixture-model",
        revision="fixture-r1",
        artifact_sha256=ACTION_MODEL_SHA,
        local_attested=attested,
    )


def test_generic_arm_rejects_history_before_transport(tmp_path) -> None:
    _, _, (manifest, history, cases, _) = _prepared_pilot(tmp_path)
    predictor = _predictor("http://127.0.0.1:9/unused")

    with pytest.raises(DataValidationError) as error:
        predictor.predict_arm(manifest, history, cases, arm="generic")

    assert error.value.code == "action_predictor_generic_history"


def test_personalized_arm_requires_exact_manifest_history(tmp_path) -> None:
    _, _, (manifest, history, cases, _) = _prepared_pilot(tmp_path)
    changed = history[0].model_copy(update={"case_id": "0" * 64})
    with action_server() as (endpoint, requests):
        predictor = _predictor(endpoint)
        with pytest.raises(DataValidationError) as error:
            predictor.predict_arm(manifest, (changed, *history[1:]), cases, arm="personalized")

    assert error.value.code == "action_predictor_history_mismatch"
    assert requests == []


def test_request_excludes_target_and_focus(tmp_path) -> None:
    _, _, (manifest, history, cases, targets) = _prepared_pilot(tmp_path)
    with action_server() as (endpoint, requests):
        predictor = _predictor(endpoint)
        predictor.predict_arm(manifest, (), cases, arm="generic")
        predictor.predict_arm(manifest, history, cases, arm="personalized")

    assert len(requests) == 12
    for request in requests:
        packet = json.loads(request["messages"][1]["content"])
        assert "target" not in packet and "focus" not in packet
        assert "hidden_target" not in packet
        assert all(target.case_id not in json.dumps(packet) for target in targets)


@pytest.mark.parametrize(
    ("model", "content"),
    [
        (
            "unexpected-model",
            '{"predicted_signal":"decision","ranking_score":0.5}',
        ),
        (
            "fixture-model",
            '{"predicted_signal":"not-allowed","ranking_score":0.5}',
        ),
    ],
)
def test_response_identity_or_schema_mismatch_is_rejected(
    tmp_path, model: str, content: str
) -> None:
    _, _, (manifest, _, cases, _) = _prepared_pilot(tmp_path)
    with action_server(model=model) as (endpoint, _):
        predictor = _predictor(endpoint)
        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr(
                "ynoy.persona_study.action_predictor.post_json",
                lambda *_args, **_kwargs: {
                    "model": model,
                    "choices": [{"message": {"content": content}}],
                },
            )
            with pytest.raises(AdapterError) as error:
                predictor.predict_arm(manifest, (), cases, arm="generic")

    assert error.value.code == "action_predictor_schema_invalid"


@pytest.mark.parametrize(
    ("endpoint", "attested", "error_type", "code"),
    [
        (
            "https://remote.invalid/v1/chat/completions",
            True,
            DataValidationError,
            "action_predictor_not_loopback",
        ),
        (
            "http://127.0.0.1:18100/v1/chat/completions",
            False,
            PolicyViolation,
            "action_predictor_attestation_required",
        ),
    ],
)
def test_predictor_requires_loopback_and_attestation(
    endpoint: str, attested: bool, error_type: type[Exception], code: str
) -> None:
    with pytest.raises(error_type) as error:
        _predictor(endpoint, attested=attested)
    assert error.value.code == code


def test_private_runner_orders_artifacts_and_refuses_overwrite(tmp_path) -> None:
    prepared, _, (_manifest, _, _, _) = _prepared_pilot(tmp_path)
    store = PersonaStudyStore(
        tmp_path / "private", real_data=False, evaluation_time=prepared.manifest.created_at
    )
    with action_server() as (endpoint, requests):
        result = run_private_action_pilot(store, prepared.manifest.run_id, _predictor(endpoint))

    assert result.run.persona_quality_claimed is False
    assert len(requests) == 12
    index = store.read_index(prepared.manifest.run_id)
    paths = [entry.relative_path for entry in index.entries]
    names = (
        "manifest.json",
        "history.json",
        "cases.json",
        "prediction-freeze.json",
        "targets.json",
        "result.json",
    )
    positions = {
        name: paths.index(f"evaluator/observable-action-pilot-0.1/{name}") for name in names
    }
    assert max(positions[name] for name in names[:3]) < positions["prediction-freeze.json"]
    assert positions["prediction-freeze.json"] < positions["targets.json"]
    assert positions["targets.json"] < positions["result.json"]
    assert result.result_relative_path.endswith("/result.json")

    with action_server() as (endpoint, _):
        with pytest.raises(DataValidationError) as error:
            run_private_action_pilot(store, prepared.manifest.run_id, _predictor(endpoint))
    assert error.value.code == "action_pilot_already_started"
