from __future__ import annotations

import json

from test_persona_reaction_benchmark import _split

from ynoy.full_persona.reaction_model_protocol import build_reaction_request
from ynoy.full_persona.reaction_profile import (
    ReactionDevelopmentProfile,
    build_reaction_profile,
    reaction_profile_prompt,
)
from ynoy.models.persona_reaction_benchmark import REACTION_SIGNALS
from ynoy.util import canonical_sha256, sha256_text


def _profile_history():
    return _split().history


def _user_packet(request: dict[str, object]) -> dict[str, object]:
    messages = request["messages"]
    assert isinstance(messages, list)
    user = messages[-1]
    assert isinstance(user, dict)
    content = user["content"]
    assert isinstance(content, str)
    return json.loads(content)


def _bounded_term_profile():
    history = tuple(
        item.model_copy(
            update={
                "context": tuple(
                    context.model_copy(
                        update={
                            "content": " ".join(
                                ["anchor", *(f"term{index}" for index in range(20))]
                            )
                        }
                    )
                    for context in item.context
                )
            }
        )
        for item in _profile_history()
    )
    profile = build_reaction_profile(history, "a" * 64)
    return profile, reaction_profile_prompt(profile)


def _near_packet_limit_inputs():
    split = _split()
    case_context = split.cases[0].context[0]
    history_context = split.history[0].context[0]
    case_value = "ş" * 300 + "c" * 1_700
    terms = " ".join(f"term{index:02d}" for index in range(8))
    history_value = ((terms + " " + "ş" * 30 + " ") * 20)[:150]

    def context(template, value, speaker="user"):
        return template.model_copy(
            update={
                "speaker": speaker,
                "content": value,
                "content_sha256": sha256_text(value),
            }
        )

    case = split.cases[0].model_copy(update={"context": (context(case_context, case_value),)})
    history = tuple(
        item.model_copy(
            update={
                "context": tuple(
                    context(
                        history_context,
                        history_value,
                        "user" if index % 2 == 0 else "assistant",
                    )
                    for index in range(4)
                ),
                "observed_response_excerpt": "b" * 240,
            }
        )
        for item in split.history[:4]
    )
    return case, history


def _large_development_profile() -> ReactionDevelopmentProfile:
    payload = {
        "development_history_sha256": "b" * 64,
        "event_count": 8_192,
        "signal_counts": {
            "correction": 2_048,
            "evidence_demand": 2_048,
            "scope_change": 1_024,
            "decision": 2_048,
            "outcome_feedback": 1_024,
        },
        "majority_signal": "decision",
        "recent_signals": ("decision",) * 12,
        "discriminative_terms": {signal: ("marker",) for signal in REACTION_SIGNALS},
        "target_data_used": False,
        "calibrated": False,
    }
    draft = ReactionDevelopmentProfile.model_construct(**payload, profile_sha256="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"profile_sha256"})
    return ReactionDevelopmentProfile.model_validate(
        {**normalized, "profile_sha256": canonical_sha256(normalized)}
    )


def test_profile_consumes_all_development_history_with_exact_counts_and_recency() -> None:
    split = _split()
    profile = build_reaction_profile(split.history, split.manifest.development_history_sha256)

    assert profile.event_count == len(split.history) == 16
    assert profile.development_history_sha256 == split.manifest.development_history_sha256
    assert profile.signal_counts == {
        "correction": 4,
        "evidence_demand": 0,
        "scope_change": 0,
        "decision": 12,
        "outcome_feedback": 0,
    }
    assert tuple(profile.signal_counts) == REACTION_SIGNALS
    assert profile.majority_signal == "decision"
    assert profile.recent_signals == (
        "decision",
        "decision",
        "decision",
        "decision",
        "decision",
        "decision",
        "decision",
        "decision",
        "correction",
        "correction",
        "correction",
        "correction",
    )


def test_profile_hash_is_canonical_and_deterministic() -> None:
    split = _split()
    first = build_reaction_profile(split.history, split.manifest.development_history_sha256)
    second = build_reaction_profile(split.history, split.manifest.development_history_sha256)

    assert first == second
    assert first.profile_sha256 == canonical_sha256(
        first.model_dump(mode="json", exclude={"profile_sha256"})
    )


def test_profile_discriminative_terms_are_bounded_and_target_free() -> None:
    profile, prompt = _bounded_term_profile()

    assert tuple(profile.discriminative_terms) == REACTION_SIGNALS
    assert len(profile.discriminative_terms["decision"]) == 8
    assert all(len(terms) <= 8 for terms in profile.discriminative_terms.values())
    assert all(
        3 <= len(term) <= 32 for terms in profile.discriminative_terms.values() for term in terms
    )
    assert profile.target_data_used is False
    assert profile.calibrated is False
    assert prompt["score_semantics"] == "development_only_unvalidated_prior"
    assert set(prompt) == {
        "event_count",
        "signal_counts",
        "majority_signal",
        "recent_signals",
        "discriminative_terms",
        "score_semantics",
    }
    assert set(profile.model_dump(mode="json")) == {
        "protocol_version",
        "development_history_sha256",
        "event_count",
        "signal_counts",
        "majority_signal",
        "recent_signals",
        "discriminative_terms",
        "target_data_used",
        "calibrated",
        "profile_sha256",
    }


def test_structured_request_includes_profile_generic_request_does_not_and_stays_bounded() -> None:
    split = _split()
    profile = build_reaction_profile(split.history, split.manifest.development_history_sha256)
    structured = build_reaction_request(
        "ynoy-test-local-8b",
        split.cases[0],
        split.history,
        "structured_persona",
        profile,
    )
    generic = build_reaction_request("ynoy-test-local-8b", split.cases[0], (), "generic_local_8b")
    structured_packet = _user_packet(structured)
    generic_packet = _user_packet(generic)

    expected_profile = json.loads(json.dumps(reaction_profile_prompt(profile)))
    assert structured_packet["development_profile"] == expected_profile
    assert generic_packet["development_profile"] is None
    assert (
        len(json.dumps(structured_packet, ensure_ascii=False, separators=(",", ":")).encode())
        <= 8 * 1024
    )


def test_maximum_reaction_packet_stays_below_byte_cap_with_bounded_history_and_profile() -> None:
    case, history = _near_packet_limit_inputs()
    profile = build_reaction_profile(history, "a" * 64)

    request = build_reaction_request(
        "ynoy-test-local-8b", case, history, "structured_persona", profile
    )
    packet = _user_packet(request)
    packet_bytes = len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode())

    assert packet_bytes <= 8 * 1024
    assert len(packet["context"]) == 1
    assert len(packet["context"][0]["content"]) == 1_200
    assert len(packet["history"]) == 4
    assert {item["evidence_id"] for item in packet["history"]} == {
        item.evidence_id for item in history
    }
    assert all(len(item["prior_context"]) == 3 for item in packet["history"])
    assert all(
        sum(len(context["content"]) for context in item["prior_context"]) <= 400
        for item in packet["history"]
    )
    assert all(len(item["user_reaction_excerpt"]) == 160 for item in packet["history"])
    assert packet["development_profile"] == json.loads(json.dumps(reaction_profile_prompt(profile)))
    assert profile.event_count == 4
    assert all(len(terms) <= 8 for terms in profile.discriminative_terms.values())


def test_8192_event_profile_stays_within_prompt_packet_byte_cap() -> None:
    split = _split()
    profile = _large_development_profile()

    request = build_reaction_request(
        "ynoy-test-local-8b",
        split.cases[0],
        split.history,
        "structured_persona",
        profile,
    )
    packet = _user_packet(request)
    packet_bytes = len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode())

    assert profile.event_count == 8_192
    assert packet["development_profile"]["event_count"] == 8_192
    assert packet_bytes <= 8 * 1024


def test_changing_late_history_changes_profile_and_structured_request() -> None:
    split = _split()
    original = build_reaction_profile(split.history, split.manifest.development_history_sha256)
    changed_history = (
        *split.history[:-1],
        split.history[-1].model_copy(update={"observed_signal": "decision"}),
    )
    changed = build_reaction_profile(
        changed_history, canonical_sha256([item.history_sha256 for item in changed_history])
    )

    original_request = build_reaction_request(
        "ynoy-test-local-8b", split.cases[0], split.history, "structured_persona", original
    )
    changed_request = build_reaction_request(
        "ynoy-test-local-8b", split.cases[0], changed_history, "structured_persona", changed
    )

    assert changed.event_count == original.event_count
    assert changed.signal_counts["decision"] == original.signal_counts["decision"] + 1
    assert changed.signal_counts["correction"] == original.signal_counts["correction"] - 1
    assert changed.profile_sha256 != original.profile_sha256
    assert _user_packet(changed_request) != _user_packet(original_request)
