from __future__ import annotations

import json

from test_persona_reaction_benchmark import _split
from test_persona_reaction_scoring import _MODEL_BINDINGS, _predictions, _target_set

from ynoy.cli.handlers.study_full_persona_benchmark import _safe_summary
from ynoy.cli.parser import parse_args
from ynoy.full_persona.reaction_scoring import (
    freeze_reaction_predictions,
    score_reaction_predictions,
)
from ynoy.models.persona_reaction_benchmark import REACTION_ARMS


def test_benchmark_parser_exposes_the_study_command() -> None:
    parsed = parse_args(["study", "benchmark-full-persona", "a" * 64])

    assert parsed.command == "study"
    assert parsed.study_command == "benchmark-full-persona"
    assert parsed.run_id == "a" * 64


def test_benchmark_safe_summary_contains_only_redacted_six_arm_metrics() -> None:
    split = _split()
    frozen = freeze_reaction_predictions(
        split.manifest,
        split.target_seal,
        cases=split.cases,
        predictions=_predictions(split),
        model_bindings=_MODEL_BINDINGS,
    )
    result = score_reaction_predictions(frozen, _target_set(split, frozen))
    summary = _safe_summary(result)

    assert summary["status"] == "inconclusive"
    assert summary["calibrated"] is False
    assert summary["persona_quality_claimed"] is False
    assert summary["authority"] == "none"
    assert summary["action_status"] == "not_performed"
    assert summary["private_content_emitted"] is False
    assert summary["private_path_emitted"] is False
    assert set(summary["arms"]) == set(REACTION_ARMS)
    assert all(
        set(metrics) == {"correct", "wrong", "abstained", "coverage", "risk", "matched_risk"}
        for metrics in summary["arms"].values()
    )

    encoded = json.dumps(summary, ensure_ascii=False)
    assert "sha256" not in encoded
    assert "target_text" not in encoded
    assert "source_key" not in encoded
    assert "target_content" not in encoded
