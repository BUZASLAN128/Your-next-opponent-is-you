# ruff: noqa: RUF001 -- Turkish contract strings are intentional.

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from support.persona_pack import built_pack, pack_atoms
from test_persona_responder import responder_server

from ynoy.errors import AdapterError, DataValidationError
from ynoy.full_persona.responder import LocalPersonaResponder
from ynoy.full_persona.response_context import select_response_context
from ynoy.full_persona.response_protocol import build_response_request
from ynoy.models.persona_response import response_hashes
from ynoy.util import canonical_sha256

MODEL = "ynoy-persona-fixture"
MODEL_SHA = "a" * 64


def responder(
    endpoint: str = "http://127.0.0.1:18100/v1/chat/completions",
) -> LocalPersonaResponder:
    return LocalPersonaResponder(
        endpoint=endpoint,
        model=MODEL,
        revision="fixture-r1",
        artifact_sha256=MODEL_SHA,
        local_attested=True,
    )


def response(used_atom_ids: list[str]) -> dict[str, object]:
    return {
        "model": MODEL,
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "response_text": "Synthetic bounded response.",
                            "used_atom_ids": used_atom_ids,
                            "uncertainties": ["synthetic fixture; not calibrated"],
                            "should_abstain": True,
                        }
                    )
                }
            }
        ],
    }


def atom_ids(value: object) -> set[str]:
    if isinstance(value, str):
        try:
            return atom_ids(json.loads(value))
        except json.JSONDecodeError:
            return set()
    if isinstance(value, dict):
        found = {str(value["atom_id"])} if "atom_id" in value else set()
        return found | {item for child in value.values() for item in atom_ids(child)}
    if isinstance(value, (list, tuple)):
        return {item for child in value for item in atom_ids(child)}
    return set()


def test_responder_materialization_is_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    monkeypatch.setattr(
        "ynoy.full_persona.responder.post_json", lambda *_args, **_kwargs: response([])
    )
    first = responder().respond(pack, "same query", arm="generic")
    second = responder().respond(pack, "same query", arm="generic")
    assert first == second
    assert first.response_sha256 == second.response_sha256
    assert first.uncertainties == (
        "Bu kontrol koluna kişisel kanıt verilmedi.",
        "Çıktı kalibre edilmemiştir.",
    )


def test_stopword_only_turkish_project_query_selects_no_atoms(tmp_path: Any) -> None:
    pack = built_pack(tmp_path)[3]
    query = "bana bir bu da de için ile kısa net proje projede cevap ver ve"
    assert select_response_context(pack, query) == ()


def test_named_relevant_query_selects_at_most_eight_direct_atoms(tmp_path: Any) -> None:
    pack = built_pack(tmp_path)[3]
    context = select_response_context(pack, "Python")
    assert 0 < len(context) <= 8
    assert all(item.source_role == "direct_user_expression" for item in context)


def test_response_schema_uses_supported_bounds_and_supplied_id_enum(tmp_path: Any) -> None:
    pack = built_pack(tmp_path)[3]
    context = select_response_context(pack, "Python")
    structured = build_response_request("fixture", "Python", context, "structured")
    generic = build_response_request("fixture", "Python", (), "generic")
    assert structured["seed"] == 0
    assert generic["seed"] == 0
    assert structured["max_tokens"] == 768
    assert "response_format" not in structured
    assert all(item.atom_id not in structured["grammar"] for item in context)
    assert 'id ::= "\\"c01\\""' in structured["grammar"]
    assert all(item.atom_id not in generic["grammar"] for item in context)
    assert 'id-array ::= "[]"' in generic["grammar"]


def test_runtime_guard_answers_corpus_residency_without_atoms_or_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]

    def unexpected(*_: object, **__: object) -> object:
        raise AssertionError("deterministic runtime guard reached model transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    result = responder().respond(
        pack,
        "50 GB corpus konuşmalarını RAM'e yüklemek sığar mı?",
        arm="structured",
    )

    assert result.generation_source == "deterministic_runtime_guard"
    assert result.used_atom_ids == ()
    assert result.evidence_receipts == ()
    assert "diskten akışla" in result.response_text
    assert "RAM" in result.response_text


def test_biography_projection_quotes_evidence_and_never_calls_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]

    def unexpected(*_: object, **__: object) -> object:
        raise AssertionError("deterministic biography projection reached model transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    result = responder().respond(
        pack,
        "Doğumumdan bugüne hayatım hakkında ne biliyorsun? Uydurma.",
        arm="structured",
    )

    assert result.generation_source == "deterministic_evidence_projection"
    assert result.used_atom_ids
    assert "Geçmiş kaydında" in result.response_text
    assert "kalanını uyduramam" in result.response_text


def test_unrelated_query_uses_local_model_and_generation_source_is_hashed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    monkeypatch.setattr(
        "ynoy.full_persona.responder.post_json", lambda *_args, **_kwargs: response([])
    )
    result = responder().respond(pack, "Python", arm="generic")
    payload = result.model_dump(mode="json", exclude={"provenance_sha256", "response_sha256"})
    expected = response_hashes(payload)
    alternate = response_hashes({**payload, "generation_source": "deterministic_runtime_guard"})

    assert result.generation_source == "local_model"
    assert (result.provenance_sha256, result.response_sha256) == expected
    assert expected != alternate


def _schema_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            key for child in value.values() for key in _schema_keys(child)
        }
    if isinstance(value, list):
        return {key for child in value for key in _schema_keys(child)}
    return set()


def test_structured_responder_round_trips_through_loopback_fixture(tmp_path: Any) -> None:
    pack = built_pack(tmp_path)[3]
    with responder_server() as (endpoint, requests):
        result = responder(endpoint=endpoint).respond(
            pack, "What should I do about Python?", arm="structured"
        )

    assert len(requests) == 1
    assert result.target_seen is False


def test_responder_rejects_model_false_abstention_before_materialization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]

    def false_abstention() -> dict[str, object]:
        raw = response([])
        candidate = json.loads(raw["choices"][0]["message"]["content"])
        candidate["should_abstain"] = False
        raw["choices"][0]["message"]["content"] = json.dumps(candidate)
        return raw

    monkeypatch.setattr(
        "ynoy.full_persona.responder.post_json", lambda *_args, **_kwargs: false_abstention()
    )
    with pytest.raises(AdapterError) as blocked:
        responder().respond(pack, "bounded query", arm="generic")
    assert blocked.value.code == "persona_responder_schema_invalid"


def test_responder_rejects_tampered_pack_before_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3].model_copy(update={"pack_sha256": "f" * 64})
    calls = 0

    def unexpected(*_: object, **__: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("tampered pack reached transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    with pytest.raises(DataValidationError) as blocked:
        responder().respond(pack, "bounded query", arm="generic")
    assert blocked.value.code == "persona_responder_pack_invalid"
    assert calls == 0


def test_responder_rejects_expired_canonical_pack_before_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    expired_base = pack.model_copy(update={"expires_at": expired_at})
    payload = expired_base.model_dump(mode="json", exclude={"pack_sha256"})
    expired = expired_base.model_copy(update={"pack_sha256": canonical_sha256(payload)})
    calls = 0

    def unexpected(*_: object, **__: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("expired pack reached transport")

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", unexpected)
    with pytest.raises(DataValidationError) as blocked:
        responder().respond(expired, "bounded query", arm="generic")
    assert blocked.value.code == "persona_responder_pack_expired"
    assert calls == 0


def test_response_provenance_contains_receipts_only_for_cited_atoms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    pack = built_pack(tmp_path)[3]
    atoms = {atom.atom_id: atom for atom in pack_atoms(pack)}
    requests: list[dict[str, object]] = []

    def transport(_: str, payload: dict[str, object], **__: object) -> dict[str, object]:
        requests.append(payload)
        supplied = sorted(atom_ids(payload))
        assert supplied
        return response(supplied[:1])

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", transport)
    first = responder().respond(pack, "What should I do about Python?", arm="structured")
    second = responder().respond(pack, "What should I do about Python?", arm="structured")

    assert len(requests) == 2
    cited_id = first.used_atom_ids[0]
    assert first.evidence_receipts == tuple(sorted(atoms[cited_id].evidence_receipts))
    assert first.used_atom_ids == (cited_id,)
    assert first.provenance_sha256 == second.provenance_sha256
    assert first.response_sha256 == second.response_sha256
