from __future__ import annotations

import json

import pytest
from support.persona_assisted import (
    CANDIDATE_FIELDS,
    MODEL_SHA,
    candidate,
    judgment,
    local_proposer,
    presentation,
    response,
)

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.persona_study.local_proposer import LocalPersonaProposer


def test_local_proposer_requires_attestation_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        "ynoy.persona_study.local_proposer.post_json", lambda *args, **kwargs: calls.append(args)
    )

    with pytest.raises(PolicyViolation) as blocked:
        local_proposer(attested=False)

    assert blocked.value.code == "persona_proposer_attestation_required"
    assert calls == []


@pytest.mark.parametrize(
    ("endpoint", "sha", "code"),
    [
        (
            "https://model.example.invalid/v1/chat/completions",
            MODEL_SHA,
            "persona_proposer_not_loopback",
        ),
        (
            "http://127.0.0.1:18100/v1/chat/completions",
            "bad",
            "persona_proposer_identity_invalid",
        ),
    ],
)
def test_local_proposer_requires_loopback_and_pinned_identity(
    endpoint: str, sha: str, code: str
) -> None:
    with pytest.raises(DataValidationError) as blocked:
        LocalPersonaProposer(
            endpoint=endpoint,
            model="fixture",
            revision="revision",
            artifact_sha256=sha,
            local_attested=True,
        )
    assert blocked.value.code == code


def test_local_proposer_requests_seven_fields_and_materializes_safe_judgment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = presentation()
    requests: list[dict[str, object]] = []

    def transport(_: str, payload: dict[str, object], **__: object) -> object:
        requests.append(payload)
        return response(judgment(card.focus.content))

    monkeypatch.setattr("ynoy.persona_study.local_proposer.post_json", transport)
    proposer = local_proposer()
    direct = proposer.propose(card, pass_name="direct")
    skeptical = proposer.propose(card, pass_name="skeptical")

    assert direct == skeptical
    assert [json.loads(item["messages"][1]["content"])["pass"] for item in requests] == [
        "direct",
        "skeptical",
    ]
    for request in requests:
        schema = request["response_format"]["schema"]
        assert tuple(schema["properties"]) == CANDIDATE_FIELDS
        assert schema["required"] == list(CANDIDATE_FIELDS)
        assert schema["additionalProperties"] is False
        _assert_dependent_fields_absent(schema)
    assert direct.scope.model_dump() == {
        "project": None,
        "role": None,
        "audience": None,
        "risk": "unknown",
        "temporal": None,
    }
    assert direct.rationale_spans[0].model_dump() == {
        "start": 0,
        "end": len(card.focus.content),
        "text": card.focus.content,
    }
    assert not direct.should_abstain and not direct.exclude_from_persona
    assert direct.evidence_demand_spans == () and direct.notes is None


def test_local_proposer_rejects_serving_model_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = presentation()
    raw = response(judgment(card.focus.content))
    raw["model"] = "unexpected-model"
    monkeypatch.setattr(
        "ynoy.persona_study.local_proposer.post_json", lambda *_args, **_kwargs: raw
    )

    with pytest.raises(AdapterError) as blocked:
        local_proposer().propose(card, pass_name="direct")

    assert blocked.value.code == "persona_proposer_identity_mismatch"


def _assert_dependent_fields_absent(schema: dict[str, object]) -> None:
    dependent = {
        "scope",
        "rationale_spans",
        "evidence_demand_spans",
        "should_abstain",
        "exclude_from_persona",
        "exclusion_reason",
        "notes",
    }
    assert dependent.isdisjoint(schema["properties"])


def test_local_proposer_materializes_exclusion_and_ignores_nonpersona_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = presentation()
    raw = candidate(judgment(card.focus.content, persona=False))
    raw["persona_kind"] = "preference"
    monkeypatch.setattr(
        "ynoy.persona_study.local_proposer.post_json", lambda *_args, **_kwargs: response(raw)
    )

    result = local_proposer().propose(card, pass_name="direct")

    assert result.persona_kind is None
    assert result.should_abstain and result.exclude_from_persona
    assert result.exclusion_reason == "not_self"
    assert result.rationale_spans[0].text == card.focus.content


def test_local_proposer_rejects_model_supplied_dependent_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = presentation()
    raw = candidate(judgment(card.focus.content))
    raw["rationale_spans"] = [
        {"start": 0, "end": len(card.focus.content), "text": card.focus.content}
    ]
    monkeypatch.setattr(
        "ynoy.persona_study.local_proposer.post_json", lambda *_args, **_kwargs: response(raw)
    )

    with pytest.raises(AdapterError) as blocked:
        local_proposer().propose(card, pass_name="direct")
    assert blocked.value.code == "persona_proposer_schema_invalid"
