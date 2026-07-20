from __future__ import annotations

from datetime import UTC, datetime

import pytest
from test_persona_reaction_benchmark import _dataset, _split

from ynoy.errors import DataValidationError
from ynoy.full_persona.reaction_baselines import run_reaction_baselines
from ynoy.full_persona.reaction_split import (
    build_reaction_split,
    validate_reaction_target_seal,
)
from ynoy.models.full_persona import (
    FullCorpusContext,
    FullCorpusEvidence,
    FullCorpusLimits,
    FullCorpusManifest,
)
from ynoy.models.persona_reaction_benchmark import PersonaReactionTargetSeal
from ynoy.util import canonical_sha256, sha256_text


def _tampered_evidence(kind: str):
    manifest, evidence = _dataset()
    changed = list(evidence)
    item = changed[16]
    updates: dict[str, object] = {
        "blob_sha256": "0" * 64,
        "byte_start": 65_530,
        "event_time": datetime(2027, 1, 1, tzinfo=UTC),
    }
    if kind == "duplicate":
        updates = {"evidence_id": changed[0].evidence_id}
    elif kind == "naive_time":
        updates = {"event_time": datetime(2026, 2, 1)}
    elif kind == "context":
        text = "x" * 8_193
        updates = {
            "context": (
                FullCorpusContext(speaker="user", content=text, content_sha256=sha256_text(text)),
            )
        }
    changed[16] = _reseal_evidence(item, updates)
    return manifest, changed


def _reseal_evidence(item: FullCorpusEvidence, updates: dict[str, object]) -> FullCorpusEvidence:
    payload = item.model_dump(mode="python")
    payload.update(updates)
    payload.pop("evidence_sha256", None)
    payload["context"] = tuple(
        value if isinstance(value, FullCorpusContext) else FullCorpusContext.model_validate(value)
        for value in payload["context"]
    )
    draft = FullCorpusEvidence.model_construct(**payload, evidence_sha256="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"evidence_sha256"})
    return FullCorpusEvidence.model_validate(
        {**normalized, "evidence_sha256": canonical_sha256(normalized)}
    )


def _manifest_with_record_limits(
    manifest: FullCorpusManifest, *, evidence_bytes: int, line_bytes: int
) -> FullCorpusManifest:
    limits = FullCorpusLimits.model_validate(
        manifest.limits.model_dump(mode="json")
        | {"max_evidence_bytes": evidence_bytes, "max_line_bytes": line_bytes}
    )
    payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    payload["limits"] = limits.model_dump(mode="json")
    return FullCorpusManifest.model_validate(
        {**payload, "manifest_sha256": canonical_sha256(payload)}
    )


def test_expected_manifest_hash_is_required() -> None:
    split = _split()
    with pytest.raises(DataValidationError):
        run_reaction_baselines(
            split.manifest,
            split.history,
            split.cases,
            expected_manifest_sha256="0" * 64,
        )


@pytest.mark.parametrize("kind", ("duplicate", "naive_time", "blob", "offset", "context"))
def test_evidence_source_and_shape_tampering_fails_closed(kind: str) -> None:
    manifest, evidence = _tampered_evidence(kind)
    with pytest.raises((DataValidationError, ValueError)):
        build_reaction_split(manifest, evidence)


def test_post_protected_boundary_event_fails_closed() -> None:
    manifest, evidence = _dataset()
    changed = list(evidence)
    changed[16] = _reseal_evidence(
        changed[16],
        {
            "event_time": datetime.fromtimestamp(
                manifest.holdout_boundary_session_start_ns / 1_000_000_000, tz=UTC
            )
        },
    )
    with pytest.raises((DataValidationError, ValueError)):
        build_reaction_split(manifest, changed)


def test_original_record_length_uses_line_limit_not_content_limit() -> None:
    manifest, evidence = _dataset()
    bounded = _manifest_with_record_limits(manifest, evidence_bytes=64, line_bytes=256)
    changed = list(evidence)
    assert len(changed[16].content.encode("utf-8")) <= bounded.limits.max_evidence_bytes
    changed[16] = _reseal_evidence(changed[16], {"byte_length": 128})
    assert changed[16].byte_length > bounded.limits.max_evidence_bytes
    assert len(build_reaction_split(bounded, changed).cases) == 24

    changed[16] = _reseal_evidence(changed[16], {"byte_length": 257})
    with pytest.raises(DataValidationError):
        build_reaction_split(bounded, changed)


def test_target_seal_order_and_manifest_binding_are_frozen() -> None:
    split = _split()
    reordered = split.target_seal.model_copy(
        update={"locators": tuple(reversed(split.target_seal.locators))}
    )
    with pytest.raises(DataValidationError):
        validate_reaction_target_seal(split.manifest, reordered)
    foreign = split.target_seal.model_copy(update={"manifest_sha256": "0" * 64})
    with pytest.raises(DataValidationError):
        validate_reaction_target_seal(split.manifest, foreign)


def test_resealed_locator_evidence_swap_fails_manifest_binding() -> None:
    split = _split()
    first, second = split.target_seal.locators[:2]

    def reseal(locator, evidence_id: str):
        payload = locator.model_dump(mode="json", exclude={"locator_sha256"})
        payload["evidence_id"] = evidence_id
        return type(locator).model_validate(
            {**payload, "locator_sha256": canonical_sha256(payload)}
        )

    locators = (
        reseal(first, second.evidence_id),
        reseal(second, first.evidence_id),
        *split.target_seal.locators[2:],
    )
    payload = split.target_seal.model_dump(mode="json", exclude={"seal_sha256"})
    payload["locators"] = [item.model_dump(mode="json") for item in locators]
    swapped = PersonaReactionTargetSeal.model_validate(
        {**payload, "seal_sha256": canonical_sha256(payload)}
    )
    with pytest.raises(DataValidationError):
        validate_reaction_target_seal(split.manifest, swapped)


def test_case_context_rehash_cannot_change_frozen_case_set() -> None:
    split = _split()
    case = split.cases[0]
    text = "replacement context"
    changed = case.model_copy(
        update={
            "context": (
                FullCorpusContext(speaker="user", content=text, content_sha256=sha256_text(text)),
            )
        }
    )
    payload = changed.model_dump(mode="json", exclude={"case_sha256"})
    rehashed = type(case).model_validate({**payload, "case_sha256": canonical_sha256(payload)})
    cases = (rehashed, *split.cases[1:])
    with pytest.raises(DataValidationError):
        run_reaction_baselines(
            split.manifest,
            split.history,
            cases,
            expected_manifest_sha256=split.manifest.manifest_sha256,
        )
