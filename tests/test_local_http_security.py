from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import MagicMock
from urllib.request import ProxyHandler

import pytest

from ynoy.core import mirror_predict
from ynoy.embeddings import (
    MAX_EMBEDDING_INPUT_BYTES,
    MAX_EMBEDDING_TEXTS,
    LocalOpenAIEmbeddingAdapter,
)
from ynoy.errors import AdapterError, DataValidationError
from ynoy.local_http import NoRedirectHandler, post_json
from ynoy.models import BootstrapDeclaration, CandidateKind, DataClass, Mode, ScopeRef
from ynoy.reasoner import (
    MAX_EVIDENCE_ITEM_BYTES,
    EvidenceItem,
    LocalOpenAIReasoner,
    ReasonerRequest,
)


class DeclarationMemory:
    def __init__(self, statements: tuple[str, ...]) -> None:
        self.declarations = [
            BootstrapDeclaration(
                kind=CandidateKind.PREFERENCE,
                statement=statement,
                source_name="size-fixture.json",
            )
            for statement in statements
        ]

    def list_bootstrap_declarations(self, **_: object) -> list[BootstrapDeclaration]:
        return self.declarations

    def list_active_canonical_claims(self, **_: object) -> list[object]:
        return []


@contextmanager
def serving_response(
    body: bytes = b"",
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> Iterator[tuple[str, list[str]]]:
    requests: list[str] = []
    response_headers = headers or {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requests.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(status)
            for name, value in response_headers.items():
                self.send_header(name, value)
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
        yield f"http://{host}:{port}/adapter", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def reasoner_request() -> ReasonerRequest:
    evidence = EvidenceItem(
        receipt_id="synthetic",
        text="bounded synthetic evidence",
        data_class="D0",
        source_kind="fixture",
    )
    return ReasonerRequest(
        mode=Mode.MIRROR,
        task="bounded task",
        task_data_class=DataClass.PUBLIC_SYNTHETIC,
        evidence=(evidence,),
    )


def test_local_http_opener_disables_environment_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_handlers: tuple[object, ...] = ()
    response = MagicMock()
    response.__enter__.return_value = response
    response.geturl.return_value = "http://127.0.0.1:8080/adapter"
    response.read.return_value = b"{}"
    opener = MagicMock()
    opener.open.return_value = response

    def capture_opener(*handlers: object) -> MagicMock:
        nonlocal captured_handlers
        captured_handlers = handlers
        return opener

    monkeypatch.setattr("ynoy.local_http.build_opener", capture_opener)
    assert (
        post_json(
            "http://127.0.0.1:8080/adapter",
            {"synthetic": True},
            timeout_seconds=1,
            max_response_bytes=64,
            error_prefix="fixture",
        )
        == {}
    )

    proxy = next(handler for handler in captured_handlers if isinstance(handler, ProxyHandler))
    assert proxy.proxies == {}
    assert any(isinstance(handler, NoRedirectHandler) for handler in captured_handlers)


def test_adapters_refuse_external_redirects_without_following() -> None:
    location = "https://model.example.invalid/escaped"
    with serving_response(status=302, headers={"Location": location}) as (endpoint, requests):
        reasoner = LocalOpenAIReasoner(endpoint=endpoint, model="fixture", is_local=True)
        with pytest.raises(AdapterError) as reasoner_error:
            reasoner.complete(reasoner_request())
        embedding = LocalOpenAIEmbeddingAdapter(endpoint=endpoint, dimensions=1, is_local=True)
        with pytest.raises(AdapterError) as embedding_error:
            embedding.embed(("synthetic",), data_class=DataClass.PUBLIC_SYNTHETIC)

    assert reasoner_error.value.code == "local_reasoner_redirect_blocked"
    assert embedding_error.value.code == "local_embedding_redirect_blocked"
    assert requests == ["/adapter", "/adapter"]


def test_adapters_fail_stably_on_oversized_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_limit = 64
    monkeypatch.setattr("ynoy.reasoner.MAX_REASONER_RESPONSE_BYTES", response_limit)
    monkeypatch.setattr("ynoy.embeddings.MAX_EMBEDDING_RESPONSE_BYTES", response_limit)
    with serving_response(b"x" * (response_limit + 1)) as (endpoint, requests):
        reasoner = LocalOpenAIReasoner(endpoint=endpoint, model="fixture", is_local=True)
        with pytest.raises(AdapterError) as reasoner_error:
            reasoner.complete(reasoner_request())
        embedding = LocalOpenAIEmbeddingAdapter(endpoint=endpoint, dimensions=1, is_local=True)
        with pytest.raises(AdapterError) as embedding_error:
            embedding.embed(("synthetic",), data_class=DataClass.PUBLIC_SYNTHETIC)

    assert reasoner_error.value.code == "local_reasoner_response_too_large"
    assert embedding_error.value.code == "local_embedding_response_too_large"
    assert requests == ["/adapter", "/adapter"]


def test_oversized_reasoner_evidence_is_rejected_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport_calls = 0

    def unexpected_transport(*_: object, **__: object) -> object:
        nonlocal transport_calls
        transport_calls += 1
        raise AssertionError("oversized evidence must not reach the transport")

    monkeypatch.setattr("ynoy.reasoner.post_json", unexpected_transport)
    reasoner = LocalOpenAIReasoner(
        endpoint="http://127.0.0.1:9/unused", model="fixture", is_local=True
    )
    per_item = "needle " + "x" * MAX_EVIDENCE_ITEM_BYTES
    with pytest.raises(DataValidationError) as item_error:
        mirror_predict(
            DeclarationMemory((per_item,)), task="needle", scope=ScopeRef(), reasoner=reasoner
        )
    item_size = 220 * 1024
    item = "needle " + "x" * (item_size - len("needle "))
    with pytest.raises(DataValidationError) as total_error:
        mirror_predict(
            DeclarationMemory((item,) * 5), task="needle", scope=ScopeRef(), reasoner=reasoner
        )

    assert item_error.value.code == "reasoner_evidence_item_too_large"
    assert total_error.value.code == "reasoner_evidence_total_too_large"
    assert transport_calls == 0


def test_oversized_embedding_input_is_rejected_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport_calls = 0

    def unexpected_transport(*_: object, **__: object) -> object:
        nonlocal transport_calls
        transport_calls += 1
        raise AssertionError("oversized embedding input must not reach the transport")

    monkeypatch.setattr("ynoy.embeddings.post_json", unexpected_transport)
    adapter = LocalOpenAIEmbeddingAdapter(
        endpoint="http://127.0.0.1:9/unused", dimensions=1, is_local=True
    )
    with pytest.raises(DataValidationError) as count_error:
        adapter.embed(
            ("x",) * (MAX_EMBEDDING_TEXTS + 1),
            data_class=DataClass.PUBLIC_SYNTHETIC,
        )
    with pytest.raises(DataValidationError) as bytes_error:
        adapter.embed(
            ("x" * (MAX_EMBEDDING_INPUT_BYTES + 1),),
            data_class=DataClass.PUBLIC_SYNTHETIC,
        )

    assert count_error.value.code == "embedding_input_too_large"
    assert bytes_error.value.code == "embedding_input_too_large"
    assert transport_calls == 0


def test_unattested_adapters_reject_d3_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reasoner_calls = 0
    embedding_calls = 0

    def reasoner_transport(*_: object, **__: object) -> object:
        nonlocal reasoner_calls
        reasoner_calls += 1
        raise AssertionError("D3 reasoner input must not reach transport")

    def embedding_transport(*_: object, **__: object) -> object:
        nonlocal embedding_calls
        embedding_calls += 1
        raise AssertionError("D3 embedding input must not reach transport")

    monkeypatch.setattr("ynoy.reasoner.post_json", reasoner_transport)
    monkeypatch.setattr("ynoy.embeddings.post_json", embedding_transport)
    evidence = EvidenceItem(
        receipt_id="private",
        text="private persona evidence",
        data_class=DataClass.DERIVED_IDENTITY,
        source_kind="fixture",
    )
    reasoner = LocalOpenAIReasoner(
        endpoint="http://127.0.0.1:9/unused", model="fixture", is_local=False
    )
    with pytest.raises(DataValidationError) as reasoner_error:
        reasoner.complete(
            ReasonerRequest(
                mode=Mode.MIRROR,
                task="private task",
                task_data_class=DataClass.PRIVATE_TASK,
                evidence=(evidence,),
            )
        )
    embedding = LocalOpenAIEmbeddingAdapter(
        endpoint="http://127.0.0.1:9/unused", dimensions=1, is_local=False
    )
    with pytest.raises(DataValidationError) as embedding_error:
        embedding.embed(("private persona",), data_class=DataClass.DERIVED_IDENTITY)

    assert reasoner_error.value.code == "external_reasoner_persona_blocked"
    assert embedding_error.value.code == "external_embedding_persona_blocked"
    assert reasoner_calls == 0 and embedding_calls == 0
