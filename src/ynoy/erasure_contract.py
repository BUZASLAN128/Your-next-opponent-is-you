from __future__ import annotations

from collections.abc import Collection

from pydantic import ValidationError

from ynoy.models import DataClass
from ynoy.models.formal_erasure import (
    DeleteSuccess,
    ErasureProducer,
    ErasureRegistry,
    ParameterInfluence,
    ParameterUpdateDecision,
    ProducerKind,
    ProducerUniverseAttestation,
)
from ynoy.util import canonical_sha256, new_id

MIGRATION_001_006_TABLES = (
    "audit_receipts",
    "benchmark_cases",
    "benchmark_manifests",
    "benchmark_predictions",
    "benchmark_runs",
    "bootstrap_declarations",
    "bootstrap_sources",
    "canonical_claims",
    "claim_admission_receipts",
    "claim_candidates",
    "claim_source_links",
    "codex_corpus_approvals",
    "codex_ingestion_checkpoints",
    "codex_ingestion_receipts",
    "codex_normalized_events",
    "continuity_events",
    "control_records",
    "corpus_blobs",
    "corpus_snapshot_files",
    "corpus_snapshot_receipts",
    "corpus_snapshots",
    "decision_events",
    "derivation_edges",
    "erasure_plans",
    "identity_candidates",
    "identity_embeddings",
    "ingestion_approvals",
    "inventory_manifests",
    "memory_corrections",
    "private_reports",
    "source_events",
    "source_receipts",
)

PRIVATE_ARTIFACT_PRODUCERS = (
    "artifact:benchmark_reports",
    "artifact:codex_inventory",
    "artifact:corpus_raw_vault",
    "artifact:full_persona_runs",
    "artifact:interaction_reviews",
    "artifact:persona_study_runs",
    "artifact:persona_study_tombstones",
    "artifact:review_corrections",
    "artifact:reviewed_states",
)


def build_default_registry() -> ErasureRegistry:
    table_producers = tuple(
        ErasureProducer(
            producer_id=f"table:ynoy.{name}",
            kind=ProducerKind.DATABASE_TABLE,
            handler_id="erasure/database-v1",
        )
        for name in MIGRATION_001_006_TABLES
    )
    artifact_producers = tuple(
        ErasureProducer(
            producer_id=name,
            kind=ProducerKind.PRIVATE_ARTIFACT,
            handler_id="erasure/private-artifact-v1",
        )
        for name in PRIVATE_ARTIFACT_PRODUCERS
    )
    producers = tuple(
        sorted((*table_producers, *artifact_producers), key=lambda item: item.producer_id)
    )
    handler_digest = canonical_sha256(
        tuple((item.producer_id, item.handler_id) for item in producers)
    )
    draft = ErasureRegistry.model_construct(
        version="erasure-registry/1",
        producers=producers,
        handler_manifest_sha256=handler_digest,
        registry_sha256="0" * 64,
    )
    return _seal_registry(draft)


def registry_parity(registry: ErasureRegistry, discovered_producers: Collection[str]) -> bool:
    registered = {item.producer_id for item in registry.producers}
    return registered == set(discovered_producers)


def build_synthetic_attestation(
    registry: ErasureRegistry,
    *,
    issued_revision: int,
    valid_through_revision: int,
) -> ProducerUniverseAttestation:
    draft = ProducerUniverseAttestation.model_construct(
        attestation_id=new_id(),
        attestor_id="synthetic-independent-attestor",
        authority="independent",
        registry_version=registry.version,
        registry_sha256=registry.registry_sha256,
        producer_ids=tuple(item.producer_id for item in registry.producers),
        handler_manifest_sha256=registry.handler_manifest_sha256,
        issued_revision=issued_revision,
        valid_through_revision=valid_through_revision,
        attestation_sha256="0" * 64,
    )
    payload = draft.model_dump(mode="python")
    payload["attestation_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"attestation_sha256"})
    )
    return ProducerUniverseAttestation.model_validate(payload)


def assess_delete_success(
    registry: ErasureRegistry,
    *,
    discovered_producers: Collection[str],
    attestation: ProducerUniverseAttestation | None,
    current_revision: int,
    database_deleted: bool,
    handlers_completed: bool,
    post_delete_independent: bool,
    fence_active: bool,
) -> DeleteSuccess:
    missing = _missing_delete_proofs(
        registry,
        discovered_producers,
        attestation,
        current_revision,
        handlers_completed,
        post_delete_independent,
        fence_active,
    )
    return DeleteSuccess(
        status="local_database_deleted" if database_deleted else "partial",
        registry_sha256=registry.registry_sha256,
        attestation_sha256=None if attestation is None else attestation.attestation_sha256,
        contract_satisfied=not missing,
        universal_success=False,
        missing_proofs=missing,
    )


def parameter_update_decision(
    influences: Collection[ParameterInfluence],
) -> ParameterUpdateDecision:
    blocked = tuple(
        sorted(
            {
                item.surface
                for item in influences
                if item.source_class != DataClass.PUBLIC_SYNTHETIC or item.transformed
            },
            key=lambda item: item.value,
        )
    )
    return ParameterUpdateDecision(
        status="private_influence_prohibited" if blocked else "not_implemented",
        blocked_surfaces=blocked,
    )


def _missing_delete_proofs(
    registry: ErasureRegistry,
    discovered: Collection[str],
    attestation: ProducerUniverseAttestation | None,
    revision: int,
    handlers_completed: bool,
    post_delete_independent: bool,
    fence_active: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not registry_parity(registry, discovered):
        missing.append("producer_registry_parity")
    if not _attestation_matches(registry, attestation, revision):
        missing.append("current_independent_attestation")
    for proof, available in (
        ("bound_handlers_completed", handlers_completed),
        ("post_delete_independence", post_delete_independent),
        ("tombstone_fence", fence_active),
    ):
        if not available:
            missing.append(proof)
    return tuple(missing)


def _attestation_matches(
    registry: ErasureRegistry,
    attestation: ProducerUniverseAttestation | None,
    revision: int,
) -> bool:
    if attestation is None:
        return False
    try:
        attestation = ProducerUniverseAttestation.model_validate(
            attestation.model_dump(mode="python")
        )
    except ValidationError:
        return False
    return (
        attestation.registry_version == registry.version
        and attestation.registry_sha256 == registry.registry_sha256
        and attestation.handler_manifest_sha256 == registry.handler_manifest_sha256
        and attestation.producer_ids == tuple(item.producer_id for item in registry.producers)
        and attestation.issued_revision <= revision <= attestation.valid_through_revision
    )


def _seal_registry(draft: ErasureRegistry) -> ErasureRegistry:
    payload = draft.model_dump(mode="python")
    payload["registry_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"registry_sha256"})
    )
    return ErasureRegistry.model_validate(payload)
