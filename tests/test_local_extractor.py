from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.extractor import LocalAtomicExtractor, _source_segments
from ynoy.interaction_review import build_interaction_review
from ynoy.models import (
    AtomicClaimProposal,
    AtomicClaimType,
    ClaimModality,
    ConfidenceDimensions,
    ConfidenceLevel,
    DataClass,
    InteractionPrompt,
    InteractionReceipt,
    NullableReviewText,
    NullReason,
    ReviewProviderEvidence,
    ScopeRef,
    SourceSpan,
    Speaker,
    SpeechAct,
    TargetLayer,
)
from ynoy.util import sha256_text

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
_RESPONSE = "Run a fast local extractor; keep persona promotion disabled."
_MODEL_SHA = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"


def _known(value: str) -> NullableReviewText:
    return NullableReviewText(value=value, authority_to_fill="user_only")


def _receipt(*, synthetic: bool = True) -> InteractionReceipt:
    prompt = "Choose a bounded extractor test."
    return InteractionReceipt(
        record_id=UUID(int=1),
        created_at=_NOW,
        source_name="synthetic-extractor",
        conversation_id="synthetic-conversation",
        turn_id="synthetic-turn",
        event_time=_NOW,
        event_time_precision="exact",
        prompt=InteractionPrompt(
            source_locator="fixture://extractor/prompt",
            speaker=Speaker.ASSISTANT,
            text=_known(prompt),
            content_sha256=sha256_text(prompt),
        ),
        response=_RESPONSE,
        response_sha256=sha256_text(_RESPONSE),
        subject_id="self",
        scope=ScopeRef(person_id="self", project="synthetic-pilot"),
        question_resolved=_known("Select a local extraction experiment."),
        source_data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.RAW_CORPUS),
        synthetic=synthetic,
    )


def _candidate(*, source_text: str = _RESPONSE) -> dict[str, object]:
    return {
        "source_text": source_text,
        "occurrence": 1,
        "literal_normalization": "Use a fast local extractor.",
        "inference": None,
        "candidate_consequence": "Benchmark one local proposal-only model.",
        "speech_act": "requirement",
        "modality": "should",
        "claim_type": "requirement",
        "target_layer": "experiment_backlog",
        "classification_confidence": "medium",
        "applicability_confidence": "unknown",
    }


def _response(*claims: dict[str, object]) -> dict[str, object]:
    return {"choices": [{"message": {"content": json.dumps({"claims": list(claims)})}}]}


def _extractor(*, attested: bool = True) -> LocalAtomicExtractor:
    return LocalAtomicExtractor(
        endpoint="http://127.0.0.1:18100/v1/chat/completions",
        model="ynoy-extractor-qwen3-8b-q4km",
        revision="7c41481f57cb95916b40956ab2f0b139b296d974",
        artifact_sha256=_MODEL_SHA,
        local_attested=attested,
    )


def test_local_extractor_builds_source_linked_unconfirmed_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def transport(_: str, payload: object, **__: object) -> object:
        requests.append(payload)
        return _response(_candidate())

    monkeypatch.setattr("ynoy.extractor.post_json", transport)
    review = _extractor().propose(_receipt(), generated_at=_NOW)

    assert review.claim_count == 1 and review.proposal_method == "local_model"
    assert review.provider_used and review.provider_evidence is not None
    assert review.provider_evidence.artifact_sha256 == _MODEL_SHA
    claim = review.claims[0]
    assert claim.source_spans[0].text == _RESPONSE
    assert _RESPONSE[
        claim.source_spans[0].character_start : claim.source_spans[0].character_end
    ] == (claim.source_spans[0].text)
    assert claim.scope.project == "synthetic-pilot"
    assert claim.status == "proposed" and claim.confirmation_required
    assert not claim.core_eligible and not review.automatic_core_promotion
    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, dict)
    response_format = request["response_format"]
    assert isinstance(response_format, dict) and response_format["type"] == "json_object"
    schema = response_format["schema"]
    assert isinstance(schema, dict)
    source_schema = schema["properties"]["claims"]["items"]["properties"]["source_text"]
    assert source_schema == {"type": "string", "enum": [_RESPONSE]}


def test_source_segments_offer_exact_numbered_items_to_model() -> None:
    source = "Context. 1- First exact item. 2) Second exact item. 3 Third exact item."

    segments = _source_segments(source)

    assert segments == (
        "Context.",
        "1- First exact item.",
        "2) Second exact item.",
        "3 Third exact item.",
    )
    assert all(segment in source for segment in segments)


def test_local_extractor_requires_attestation_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def forbidden(*_: object, **__: object) -> object:
        calls.append("called")
        raise AssertionError("unattested extractor must not call transport")

    monkeypatch.setattr("ynoy.extractor.post_json", forbidden)
    with pytest.raises(PolicyViolation) as blocked:
        _extractor(attested=False).propose(_receipt(synthetic=False), generated_at=_NOW)
    assert blocked.value.code == "local_extractor_attestation_required"
    assert calls == []


@pytest.mark.parametrize(
    ("endpoint", "sha", "code"),
    [
        ("https://model.example/v1/chat/completions", _MODEL_SHA, "local_extractor_not_loopback"),
        ("http://127.0.0.1:18100/v1/chat/completions", "bad", "local_extractor_identity_invalid"),
    ],
)
def test_local_extractor_rejects_untrusted_provider_identity(
    endpoint: str, sha: str, code: str
) -> None:
    with pytest.raises(DataValidationError) as blocked:
        LocalAtomicExtractor(
            endpoint=endpoint,
            model="fixture",
            revision="revision",
            artifact_sha256=sha,
            local_attested=True,
        )
    assert blocked.value.code == code


@pytest.mark.parametrize(
    ("response", "code"),
    [
        ({"choices": []}, "local_extractor_schema_invalid"),
        (
            _response(_candidate(source_text="fast local extractor")),
            "local_extractor_segment_invalid",
        ),
        (_response(_candidate(source_text="not in source")), "local_extractor_span_invalid"),
        (_response(_candidate(), _candidate()), "local_extractor_schema_invalid"),
    ],
)
def test_local_extractor_fails_closed_on_invalid_output(
    monkeypatch: pytest.MonkeyPatch, response: object, code: str
) -> None:
    monkeypatch.setattr("ynoy.extractor.post_json", lambda *_args, **_kwargs: response)
    data_errors = {"local_extractor_segment_invalid", "local_extractor_span_invalid"}
    error = DataValidationError if code in data_errors else AdapterError
    with pytest.raises(error) as blocked:
        _extractor().propose(_receipt(), generated_at=_NOW)
    assert blocked.value.code == code


def test_review_builder_revalidates_provider_evidence() -> None:
    receipt = _receipt()
    text = "fast local extractor"
    start = _RESPONSE.index(text)
    claim = AtomicClaimProposal(
        record_id=UUID(int=2),
        created_at=_NOW,
        receipt_id=receipt.record_id,
        subject_id="self",
        source_spans=(
            SourceSpan(character_start=start, character_end=start + len(text), text=text),
        ),
        literal_normalization="Use a fast local extractor.",
        inference=NullableReviewText(
            null_reason=NullReason.NOT_STATED, authority_to_fill="evidence_required"
        ),
        candidate_consequence=NullableReviewText(
            null_reason=NullReason.AWAITING_USER_CONFIRMATION,
            authority_to_fill="evidence_required",
        ),
        speech_act=SpeechAct.REQUIREMENT,
        modality=ClaimModality.SHOULD,
        claim_type=AtomicClaimType.REQUIREMENT,
        target_layer=TargetLayer.EXPERIMENT_BACKLOG,
        scope=receipt.scope,
        confidence=ConfidenceDimensions(
            classification=ConfidenceLevel.MEDIUM,
            applicability=ConfidenceLevel.UNKNOWN,
        ),
    )
    provider = ReviewProviderEvidence(
        model="fixture", revision="revision", artifact_sha256=_MODEL_SHA
    ).model_copy(update={"artifact_sha256": "bad"})

    with pytest.raises(DataValidationError) as blocked:
        build_interaction_review(receipt, (claim,), provider_evidence=provider)
    assert blocked.value.code == "review_provider_invalid"
