from __future__ import annotations

from collections import Counter

from ynoy.models.persona_harvest import HarvestCandidate
from ynoy.util import sha256_text


class HarvestReservoir:
    """Order-independent bounded candidate reservoir with diversity caps."""

    def __init__(
        self,
        maximum: int,
        selector_config_sha256: str,
        initial: tuple[HarvestCandidate, ...] = (),
    ) -> None:
        if maximum < 1 or len(initial) > maximum:
            raise ValueError("invalid harvest reservoir size")
        if len({item.candidate_id for item in initial}) != len(initial):
            raise ValueError("harvest reservoir candidates must be unique")
        self.maximum = maximum
        self.selector_config_sha256 = selector_config_sha256
        self._items = tuple(initial)
        self._reselect(initial)

    @property
    def candidates(self) -> tuple[HarvestCandidate, ...]:
        return self._items

    def offer(self, candidate: HarvestCandidate) -> bool:
        before = {item.candidate_id for item in self._items}
        combined = {item.candidate_id: item for item in self._items}
        combined[candidate.candidate_id] = candidate
        self._reselect(tuple(combined.values()))
        after = {item.candidate_id for item in self._items}
        return after != before

    def _reselect(self, values: tuple[HarvestCandidate, ...]) -> None:
        conversations: Counter[str] = Counter()
        months: Counter[str] = Counter()
        selected: list[HarvestCandidate] = []
        month_limit = max(2, self.maximum // 3)
        for candidate in sorted(values, key=self._rank):
            if conversations[candidate.conversation_key] >= 2:
                continue
            if months[candidate.session_month] >= month_limit:
                continue
            selected.append(candidate)
            conversations[candidate.conversation_key] += 1
            months[candidate.session_month] += 1
            if len(selected) == self.maximum:
                break
        self._items = tuple(selected)

    def _rank(self, candidate: HarvestCandidate) -> tuple[int, str, str]:
        tie = sha256_text(
            f"{self.selector_config_sha256}:{candidate.partition}:"
            f"{candidate.session_month}:{candidate.candidate_id}"
        )
        return -candidate.signal_score, tie, candidate.candidate_id
