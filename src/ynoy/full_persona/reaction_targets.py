from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError

from ynoy.errors import DataValidationError
from ynoy.full_persona.integrity import verify_committed_run
from ynoy.full_persona.reaction_contracts import CompactReactionEvent, seal_model
from ynoy.full_persona.reaction_evidence import compact_reaction_events
from ynoy.full_persona.reaction_split import validate_reaction_target_seal
from ynoy.full_persona.reader import iter_verified_evidence
from ynoy.full_persona.store import FullPersonaStore
from ynoy.models.full_persona import FullCorpusEvidence, FullCorpusHead, FullCorpusManifest
from ynoy.models.persona_reaction_benchmark import (
    PersonaReactionManifest,
    PersonaReactionTarget,
    PersonaReactionTargetSeal,
)
from ynoy.models.persona_reaction_results import (
    PersonaReactionPredictionFreeze,
    PersonaReactionTargetSet,
)


def materialize_synthetic_reaction_targets(
    source_manifest: FullCorpusManifest,
    evidence: Iterable[FullCorpusEvidence],
    reaction_manifest: PersonaReactionManifest,
    target_seal: PersonaReactionTargetSeal,
    freeze: PersonaReactionPredictionFreeze | None,
) -> PersonaReactionTargetSet:
    """Open D0 fixture targets only after a valid prediction freeze exists."""
    source, reaction, seal, checked_freeze = _validated_context(
        source_manifest, reaction_manifest, target_seal, freeze
    )
    if not source.synthetic or not reaction.synthetic or not checked_freeze.synthetic:
        raise DataValidationError(
            "reaction_target_mode_invalid", "Synthetic target path refuses private evidence."
        )
    if reaction.source_head_sha256 != source.manifest_sha256 or reaction.source_head_revision != 0:
        raise DataValidationError(
            "reaction_target_source_invalid", "Synthetic target source binding is invalid."
        )
    sources = {item.source_key: item for item in source.files}
    events = compact_reaction_events(evidence, sources, source)
    targets = _materialize(events, seal)
    return _target_set(source, reaction, seal, checked_freeze, targets)


def materialize_reaction_targets(
    store: FullPersonaStore,
    source_manifest: FullCorpusManifest,
    source_head: FullCorpusHead,
    reaction_manifest: PersonaReactionManifest,
    target_seal: PersonaReactionTargetSeal,
    freeze: PersonaReactionPredictionFreeze | None,
) -> PersonaReactionTargetSet:
    """Open private hash-only targets after verifying the committed source chain and freeze."""
    source, reaction, seal, checked_freeze = _validated_context(
        source_manifest, reaction_manifest, target_seal, freeze
    )
    if source.synthetic or reaction.synthetic or checked_freeze.synthetic:
        raise DataValidationError(
            "reaction_target_mode_invalid", "Private target path refuses synthetic evidence."
        )
    _validate_private_source(source, source_head, reaction)
    verify_committed_run(store, source, source_head)
    sources = {item.source_key: item for item in source.files}
    events = compact_reaction_events(
        iter_verified_evidence(store, source, source_head), sources, source
    )
    targets = _materialize(events, seal)
    return _target_set(source, reaction, seal, checked_freeze, targets)


def _validated_context(
    source: FullCorpusManifest,
    reaction: PersonaReactionManifest,
    seal: PersonaReactionTargetSeal,
    freeze: PersonaReactionPredictionFreeze | None,
) -> tuple[
    FullCorpusManifest,
    PersonaReactionManifest,
    PersonaReactionTargetSeal,
    PersonaReactionPredictionFreeze,
]:
    if freeze is None:
        raise DataValidationError(
            "reaction_prediction_freeze_required", "Targets cannot open before prediction freeze."
        )
    try:
        safe_source = FullCorpusManifest.model_validate(source.model_dump(mode="json"))
        safe_reaction = PersonaReactionManifest.model_validate(reaction.model_dump(mode="json"))
        safe_seal = PersonaReactionTargetSeal.model_validate(seal.model_dump(mode="json"))
        safe_freeze = PersonaReactionPredictionFreeze.model_validate(freeze.model_dump(mode="json"))
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_target_input_invalid", "Reaction target input is invalid."
        ) from exc
    validate_reaction_target_seal(safe_reaction, safe_seal)
    invalid = (
        safe_reaction.source_manifest_sha256 != safe_source.manifest_sha256
        or safe_freeze.manifest_sha256 != safe_reaction.manifest_sha256
        or safe_freeze.target_seal_sha256 != safe_seal.seal_sha256
        or safe_freeze.targets_revealed
    )
    if invalid:
        raise DataValidationError(
            "reaction_target_binding_invalid", "Target inputs do not share one frozen chain."
        )
    return safe_source, safe_reaction, safe_seal, safe_freeze


def _validate_private_source(
    source: FullCorpusManifest,
    head: FullCorpusHead,
    reaction: PersonaReactionManifest,
) -> None:
    try:
        safe_head = FullCorpusHead.model_validate(head.model_dump(mode="json"))
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "reaction_target_head_invalid", "Reaction source head is invalid."
        ) from exc
    invalid = (
        safe_head.status != "complete"
        or safe_head.run_id != source.run_id
        or safe_head.manifest_sha256 != source.manifest_sha256
        or safe_head.head_sha256 != reaction.source_head_sha256
        or safe_head.revision != reaction.source_head_revision
        or source.source_snapshot_sha256 != reaction.source_snapshot_sha256
        or source.holdout_freeze_sha256 != reaction.source_holdout_freeze_sha256
    )
    if invalid:
        raise DataValidationError(
            "reaction_target_source_invalid", "Private target source chain is invalid."
        )


def _materialize(
    events: tuple[CompactReactionEvent, ...], seal: PersonaReactionTargetSeal
) -> tuple[PersonaReactionTarget, ...]:
    by_id = {item.evidence_id: item for item in events}
    if len(by_id) != len(events):
        raise DataValidationError(
            "reaction_target_duplicate_evidence", "Reaction target evidence identifiers repeat."
        )
    targets: list[PersonaReactionTarget] = []
    for locator in seal.locators:
        item = by_id.get(locator.evidence_id)
        if item is None or item.evidence_sha256 != locator.evidence_sha256:
            raise DataValidationError(
                "reaction_target_locator_invalid", "Reaction target locator did not resolve."
            )
        payload: dict[str, object] = {
            "case_id": locator.case_id,
            "label": item.signal,
            "target_content_sha256": item.content_sha256,
            "target_evidence_sha256": item.evidence_sha256,
        }
        targets.append(seal_model(PersonaReactionTarget, payload, "target_sha256"))
    return tuple(targets)


def _target_set(
    source: FullCorpusManifest,
    reaction: PersonaReactionManifest,
    seal: PersonaReactionTargetSeal,
    freeze: PersonaReactionPredictionFreeze,
    targets: tuple[PersonaReactionTarget, ...],
) -> PersonaReactionTargetSet:
    payload: dict[str, object] = {
        "manifest_sha256": reaction.manifest_sha256,
        "prediction_freeze_sha256": freeze.freeze_sha256,
        "source_manifest_sha256": source.manifest_sha256,
        "source_head_sha256": reaction.source_head_sha256,
        "source_head_revision": reaction.source_head_revision,
        "synthetic": source.synthetic,
        "target_seal": seal,
        "targets": targets,
        "targets_revealed": True,
        "raw_target_text_persisted": False,
    }
    return seal_model(PersonaReactionTargetSet, payload, "target_set_sha256")
