from __future__ import annotations

import json
import re
from itertools import combinations

import pytest
from test_persona_reaction_benchmark import _split

from ynoy.errors import AdapterError
from ynoy.full_persona.reaction_model_protocol import (
    build_reaction_request,
    parse_reaction_envelope,
    select_reaction_history,
)

_MODEL = "ynoy-test-local-8b"


def _grammar(history=()) -> tuple[str, tuple]:
    split = _split()
    selected = select_reaction_history(split.cases[0], history) if history else ()
    request = build_reaction_request(_MODEL, split.cases[0], selected, "structured_persona")
    grammar = request["grammar"]
    assert isinstance(grammar, str)
    return grammar, selected


def _envelope(content: str) -> dict[str, object]:
    return {
        "model": _MODEL,
        "choices": [{"message": {"content": content}}],
    }


def _candidate_json() -> str:
    return json.dumps(
        {"predicted_label": "abstain", "ranking_score": 0, "evidence_ids": []},
        separators=(",", ":"),
    )


def test_generic_grammar_has_exact_fields_and_forbids_citations() -> None:
    grammar, selected = _grammar()
    assert selected == ()
    object_rule = next(line for line in grammar.splitlines() if line.startswith("object ::="))
    assert re.findall(r'\\"([a-z_]+)\\":', object_rule) == [
        "predicted_label",
        "ranking_score",
        "evidence_ids",
    ]
    assert 'evidence-array ::= "[]"' in grammar
    assert "evidence ::=" not in grammar


def test_structured_grammar_allows_only_sorted_unique_supplied_subsets() -> None:
    split = _split()
    grammar, selected = _grammar(split.history)
    supplied = {item.evidence_id for item in selected}
    assert len(supplied) == 4
    assert all(evidence_id in grammar for evidence_id in supplied)
    assert all(
        item.evidence_id not in grammar
        for item in split.history
        if item.evidence_id not in supplied
    )
    array_rule = next(
        line for line in grammar.splitlines() if line.startswith("evidence-array ::=")
    )
    ordered = tuple(sorted(supplied))
    arrays = (
        "[]",
        *(
            json.dumps(values, separators=(",", ":"))
            for size in range(1, len(ordered) + 1)
            for values in combinations(ordered, size)
        ),
    )
    assert array_rule == "evidence-array ::= " + " | ".join(json.dumps(value) for value in arrays)
    duplicate = json.dumps((ordered[0], ordered[0]), separators=(",", ":"))
    unsorted = json.dumps((ordered[1], ordered[0]), separators=(",", ":"))
    assert json.dumps(duplicate) not in array_rule
    assert json.dumps(unsorted) not in array_rule


def test_empty_think_wrapper_before_strict_json_is_accepted() -> None:
    content = f"<think>\n\n</think>\n\n{_candidate_json()}"
    candidate = parse_reaction_envelope(_envelope(content), _MODEL, set())
    assert candidate.predicted_label == "abstain"
    assert candidate.evidence_ids == ()


@pytest.mark.parametrize(
    "content",
    (
        f"<think>hidden reasoning</think>{_candidate_json()}",
        f"prefix {_candidate_json()}",
        f"{_candidate_json()} suffix",
    ),
)
def test_nonempty_thinking_or_extra_prose_fails_closed(content: str) -> None:
    with pytest.raises(AdapterError):
        parse_reaction_envelope(_envelope(content), _MODEL, set())
