from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, TypeAdapter

from ynoy.models.base import DataClass
from ynoy.models.full_persona import FullCorpusContext, FullCorpusManifest
from ynoy.models.persona_reaction_benchmark import (
    REACTION_ARMS,
    REACTION_SIGNALS,
    PersonaReactionCase,
    PersonaReactionHistory,
    PersonaReactionManifest,
    PersonaReactionTargetLocator,
    PersonaReactionTargetSeal,
    ReactionSignal,
)
from ynoy.util import canonical_sha256

_JSON_OBJECT = TypeAdapter(dict[str, Any])


@dataclass(frozen=True, slots=True)
class CompactReactionEvent:
    evidence_id: str
    evidence_sha256: str
    event_time: datetime
    source_key: str
    source_receipt: str
    conversation_key: str
    lineage_component_receipt: str
    context: tuple[FullCorpusContext, ...]
    content_excerpt: str
    content_sha256: str
    signal: ReactionSignal


def build_history(
    item: CompactReactionEvent, *, data_class: DataClass, synthetic: bool
) -> PersonaReactionHistory:
    payload = {
        "history_id": canonical_sha256({"evidence_id": item.evidence_id, "role": "development"}),
        "evidence_id": item.evidence_id,
        "event_time": item.event_time,
        "source_key": item.source_key,
        "source_receipt": item.source_receipt,
        "conversation_key": item.conversation_key,
        "lineage_component_receipt": item.lineage_component_receipt,
        "context": item.context,
        "observed_response_excerpt": item.content_excerpt,
        "content_sha256": item.content_sha256,
        "observed_signal": item.signal,
        "data_class": data_class,
        "synthetic": synthetic,
    }
    return seal_model(PersonaReactionHistory, payload, "history_sha256")


def build_case(
    run_id: str, item: CompactReactionEvent, *, data_class: DataClass, synthetic: bool
) -> PersonaReactionCase:
    payload = {
        "case_id": canonical_sha256({"run_id": run_id, "evidence_id": item.evidence_id}),
        "event_time": item.event_time,
        "source_key": item.source_key,
        "source_receipt": item.source_receipt,
        "conversation_key": item.conversation_key,
        "lineage_component_receipt": item.lineage_component_receipt,
        "context": item.context,
        "data_class": data_class,
        "synthetic": synthetic,
    }
    return seal_model(PersonaReactionCase, payload, "case_sha256")


def build_manifest(
    source: FullCorpusManifest,
    history: tuple[PersonaReactionHistory, ...],
    cases: tuple[PersonaReactionCase, ...],
    cutoff: datetime,
    *,
    source_head_sha256: str,
    source_head_revision: int,
    evidence_authentication: str,
) -> PersonaReactionManifest:
    payload = {
        "protocol_version": "sealed-reaction-benchmark/0.1",
        "source_run_id": source.run_id,
        "source_manifest_sha256": source.manifest_sha256,
        "source_snapshot_sha256": source.source_snapshot_sha256,
        "source_head_sha256": source_head_sha256,
        "source_head_revision": source_head_revision,
        "source_holdout_freeze_sha256": source.holdout_freeze_sha256,
        "temporal_cutoff": cutoff,
        "development_history_ids": tuple(item.history_id for item in history),
        "development_history_sha256": canonical_sha256([item.history_sha256 for item in history]),
        "sealed_case_ids": tuple(item.case_id for item in cases),
        "sealed_case_set_sha256": canonical_sha256([item.case_sha256 for item in cases]),
        "sealed_cluster_count": len({item.lineage_component_receipt for item in cases}),
        "max_cases_per_component": 3,
        "signal_tie_order": REACTION_SIGNALS,
        "arms": REACTION_ARMS,
        "data_class": source.source_data_class,
        "synthetic": source.synthetic,
        "evidence_authentication": evidence_authentication,
        "split_scope": "internal_pre_protected_holdout",
        "label_semantics": "lexical_proxy_not_user_validated",
        "protected_future_holdout_used": False,
        "target_visible_to_predictors": False,
        "local_only": True,
        "external_calls": (),
        "persona_identity_claimed": False,
        "calibration_used": False,
        "semantic_adoption_claimed": False,
        "automatic_core_promotion": False,
    }
    return seal_model(PersonaReactionManifest, payload, "manifest_sha256")


def build_target_seal(
    manifest: PersonaReactionManifest,
    sealed: tuple[CompactReactionEvent, ...],
    cases: tuple[PersonaReactionCase, ...],
) -> PersonaReactionTargetSeal:
    locators = tuple(
        seal_model(
            PersonaReactionTargetLocator,
            {
                "case_id": case.case_id,
                "evidence_id": item.evidence_id,
                "evidence_sha256": item.evidence_sha256,
            },
            "locator_sha256",
        )
        for item, case in zip(sealed, cases, strict=True)
    )
    return seal_model(
        PersonaReactionTargetSeal,
        {
            "manifest_sha256": manifest.manifest_sha256,
            "locators": locators,
            "targets_revealed": False,
        },
        "seal_sha256",
    )


def seal_model[ModelT: BaseModel](
    model: type[ModelT], payload: dict[str, object], hash_field: str
) -> ModelT:
    normalized = _JSON_OBJECT.dump_python(payload, mode="json")
    return model.model_validate({**normalized, hash_field: canonical_sha256(normalized)})
