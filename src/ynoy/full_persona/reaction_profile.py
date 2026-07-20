# ruff: noqa: RUF001 -- Turkish tokenization vocabulary is intentional.

from __future__ import annotations

import re
from collections import Counter
from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from ynoy.models.base import StrictModel
from ynoy.models.persona_reaction_benchmark import (
    REACTION_SIGNALS,
    PersonaReactionHistory,
    ReactionSignal,
)
from ynoy.util import canonical_sha256

type ProfileTerm = Annotated[
    str, StringConstraints(pattern=r"^[\wçğıöşü-]+$", min_length=3, max_length=32)
]

_TOKEN = re.compile(r"[\wçğıöşü-]+", re.I)
_MAX_TERMS_PER_SIGNAL = 8
_RECENT_SIGNAL_COUNT = 12
_STOPWORDS = {
    "about",
    "ama",
    "bana",
    "ben",
    "bir",
    "biz",
    "bu",
    "da",
    "de",
    "gibi",
    "için",
    "ile",
    "mı",
    "mi",
    "mu",
    "mü",
    "nasıl",
    "olarak",
    "sonra",
    "the",
    "ve",
}


class ReactionDevelopmentProfile(StrictModel):
    protocol_version: str = "reaction-development-profile/0.1"
    development_history_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_count: int = Field(ge=1, le=8_192)
    signal_counts: dict[ReactionSignal, int]
    majority_signal: ReactionSignal
    recent_signals: tuple[ReactionSignal, ...] = Field(max_length=_RECENT_SIGNAL_COUNT)
    discriminative_terms: dict[ReactionSignal, tuple[ProfileTerm, ...]]
    target_data_used: bool = False
    calibrated: bool = False
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_is_canonical(self) -> ReactionDevelopmentProfile:
        if tuple(self.signal_counts) != REACTION_SIGNALS:
            raise ValueError("reaction profile signal order changed")
        if tuple(self.discriminative_terms) != REACTION_SIGNALS:
            raise ValueError("reaction profile term order changed")
        if sum(self.signal_counts.values()) != self.event_count:
            raise ValueError("reaction profile event count is inconsistent")
        if self.target_data_used or self.calibrated:
            raise ValueError("reaction profile cannot use targets or claim calibration")
        payload = self.model_dump(mode="json", exclude={"profile_sha256"})
        if self.profile_sha256 != canonical_sha256(payload):
            raise ValueError("reaction profile hash does not match")
        return self


def build_reaction_profile(
    history: tuple[PersonaReactionHistory, ...], development_history_sha256: str
) -> ReactionDevelopmentProfile:
    counts = Counter(item.observed_signal for item in history)
    global_terms: Counter[str] = Counter()
    by_signal = {signal: Counter[str]() for signal in REACTION_SIGNALS}
    for item in history:
        terms = _context_terms(item)
        global_terms.update(terms)
        by_signal[item.observed_signal].update(terms)
    signal_counts = {signal: counts[signal] for signal in REACTION_SIGNALS}
    payload: dict[str, Any] = {
        "development_history_sha256": development_history_sha256,
        "event_count": len(history),
        "signal_counts": signal_counts,
        "majority_signal": _majority(signal_counts),
        "recent_signals": tuple(item.observed_signal for item in history[-_RECENT_SIGNAL_COUNT:]),
        "discriminative_terms": {
            signal: _top_terms(by_signal[signal], global_terms) for signal in REACTION_SIGNALS
        },
        "target_data_used": False,
        "calibrated": False,
    }
    draft = ReactionDevelopmentProfile.model_construct(**payload, profile_sha256="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"profile_sha256"})
    return ReactionDevelopmentProfile.model_validate(
        {**normalized, "profile_sha256": canonical_sha256(normalized)}
    )


def reaction_profile_prompt(profile: ReactionDevelopmentProfile) -> dict[str, object]:
    return {
        "event_count": profile.event_count,
        "signal_counts": profile.signal_counts,
        "majority_signal": profile.majority_signal,
        "recent_signals": profile.recent_signals,
        "discriminative_terms": profile.discriminative_terms,
        "score_semantics": "development_only_unvalidated_prior",
    }


def _context_terms(item: PersonaReactionHistory) -> set[str]:
    return {token for context in item.context for token in _tokens(context.content)}


def _tokens(value: str) -> set[str]:
    return {
        normalized
        for item in _TOKEN.findall(value)
        if len(normalized := item.casefold()) >= 3 and normalized not in _STOPWORDS
    }


def _top_terms(values: Counter[str], global_terms: Counter[str]) -> tuple[str, ...]:
    candidates = (
        term for term, count in values.items() if count >= 2 and global_terms[term] >= count
    )
    ranked = sorted(
        candidates,
        key=lambda term: (
            -(1000 * values[term] // global_terms[term]),
            -values[term],
            term,
        ),
    )
    return tuple(ranked[:_MAX_TERMS_PER_SIGNAL])


def _majority(counts: dict[ReactionSignal, int]) -> ReactionSignal:
    order = {signal: index for index, signal in enumerate(REACTION_SIGNALS)}
    return sorted(REACTION_SIGNALS, key=lambda signal: (-counts[signal], order[signal]))[0]
