from __future__ import annotations

from typing import Any

from test_persona_reaction_benchmark import _split

from ynoy.full_persona.reaction_baselines import run_reaction_baselines
from ynoy.models.full_persona import FullCorpusContext
from ynoy.models.persona_reaction_benchmark import (
    PersonaReactionCase,
    PersonaReactionHistory,
    PersonaReactionManifest,
)
from ynoy.util import canonical_sha256, sha256_text


def _context(text: str) -> FullCorpusContext:
    return FullCorpusContext(
        speaker="user",
        content=text,
        content_sha256=sha256_text(text),
    )


def _history_variant(
    item: PersonaReactionHistory,
    *,
    signal: str,
    marker: str,
) -> PersonaReactionHistory:
    payload = item.model_dump(mode="json")
    payload.update(observed_signal=signal, context=(_context(marker).model_dump(mode="json"),))
    payload.pop("history_sha256")
    return PersonaReactionHistory.model_validate(
        {**payload, "history_sha256": canonical_sha256(payload)}
    )


def _case_variant(item: PersonaReactionCase, marker: str) -> PersonaReactionCase:
    payload = item.model_dump(mode="json")
    payload["context"] = (_context(marker).model_dump(mode="json"),)
    payload.pop("case_sha256")
    return PersonaReactionCase.model_validate({**payload, "case_sha256": canonical_sha256(payload)})


def _manifest_variant(
    manifest: PersonaReactionManifest,
    history: tuple[PersonaReactionHistory, ...],
    cases: tuple[PersonaReactionCase, ...],
) -> PersonaReactionManifest:
    payload: dict[str, Any] = manifest.model_dump(mode="json")
    payload.update(
        development_history_ids=tuple(item.history_id for item in history),
        development_history_sha256=canonical_sha256([item.history_sha256 for item in history]),
        sealed_case_ids=tuple(item.case_id for item in cases),
        sealed_case_set_sha256=canonical_sha256([item.case_sha256 for item in cases]),
    )
    payload.pop("manifest_sha256")
    return PersonaReactionManifest.model_validate(
        {**payload, "manifest_sha256": canonical_sha256(payload)}
    )


def _independent_inputs() -> tuple[
    PersonaReactionManifest,
    tuple[PersonaReactionHistory, ...],
    tuple[PersonaReactionCase, ...],
]:
    original = _split()
    history = tuple(
        _history_variant(
            item,
            signal="decision" if index < 10 else "correction",
            marker=("decision signal stable" if index < 10 else "correction signal stable"),
        )
        for index, item in enumerate(original.history)
    )
    cases = list(original.cases)
    cases[0] = _case_variant(cases[0], "correction signal stable")
    case_models = tuple(cases)
    manifest = _manifest_variant(original.manifest, history, case_models)
    return manifest, history, case_models


def test_static_profile_scores_signal_markers_instead_of_copying_majority() -> None:
    manifest, history, cases = _independent_inputs()
    run = run_reaction_baselines(
        manifest,
        history,
        cases,
        expected_manifest_sha256=manifest.manifest_sha256,
    )
    majority = run.arms["history_majority"][0]
    static = run.arms["static_profile"][0]
    correction_ids = {item.evidence_id for item in history if item.observed_signal == "correction"}

    assert majority.predicted_label == "decision"
    assert static.predicted_label == "correction"
    assert static.predicted_label != majority.predicted_label
    assert set(static.evidence_ids).issubset({item.evidence_id for item in history})
    assert set(static.evidence_ids) & correction_ids
