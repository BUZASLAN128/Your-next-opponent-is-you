from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from ynoy.erasure_contract import (
    MIGRATION_001_006_TABLES,
    assess_delete_success,
    build_default_registry,
    build_synthetic_attestation,
    parameter_update_decision,
    registry_parity,
)
from ynoy.errors import PolicyViolation
from ynoy.models import DataClass
from ynoy.models.formal_erasure import (
    ErasureTombstone,
    ParameterInfluence,
    ParameterInfluenceSurface,
    ProducerUniverseAttestation,
)
from ynoy.synthetic_erasure import SyntheticErasureStore
from ynoy.util import new_id


def _producer_ids(registry) -> set[str]:
    return {item.producer_id for item in registry.producers}


def _assessment(registry, universe, attestation=None, *, revision: int = 1):
    return assess_delete_success(
        registry,
        discovered_producers=universe,
        attestation=attestation,
        current_revision=revision,
        database_deleted=True,
        handlers_completed=True,
        post_delete_independent=True,
        fence_active=True,
    )


def test_unregistered_private_producer_breaks_erasure_parity() -> None:
    registry = build_default_registry()
    discovered = _producer_ids(registry) | {"table:ynoy.unregistered_private_state"}

    assert not registry_parity(registry, discovered)
    result = _assessment(registry, discovered)
    assert not result.contract_satisfied
    assert "producer_registry_parity" in result.missing_proofs
    assert not result.universal_success


def test_erasure_requires_current_bound_producer_universe_attestation() -> None:
    registry = build_default_registry()
    universe = _producer_ids(registry)
    valid = build_synthetic_attestation(registry, issued_revision=1, valid_through_revision=2)

    assert _assessment(registry, universe, valid, revision=2).contract_satisfied
    assert not _assessment(registry, universe, None).contract_satisfied
    assert not _assessment(registry, universe, valid, revision=3).contract_satisfied
    rebound = valid.model_copy(update={"registry_version": "other-registry"})
    assert not _assessment(registry, universe, rebound).contract_satisfied
    with pytest.raises(ValidationError):
        ProducerUniverseAttestation.model_validate(
            {**valid.model_dump(mode="python"), "authority": "self_declared"}
        )


def test_post_delete_independence_covers_admissible_future_traces() -> None:
    registry = build_default_registry()
    store = SyntheticErasureStore(registry_version=registry.version)
    source_id = new_id()
    store.ingest(source_id)
    store.create_derivative(source_id, new_id())
    store.delete(source_id, revision=1)
    schedules = ("retry", "import", "restore", "recovery")

    first = store.future_trace(
        source_id, schedules=schedules, counterfactual_private_state=object()
    )
    second = store.future_trace(
        source_id, schedules=schedules, counterfactual_private_state=object()
    )

    assert first == second
    assert all(
        item.derivation == "blocked_tombstone" and item.external_calls == 0 for item in first
    )


def test_tombstone_blocks_post_delete_derivative() -> None:
    registry = build_default_registry()
    store = SyntheticErasureStore(registry_version=registry.version)
    source_id = new_id()
    store.ingest(source_id)
    store.delete(source_id, revision=1)

    with pytest.raises(PolicyViolation) as derivative:
        store.create_derivative(source_id, new_id())
    with pytest.raises(PolicyViolation) as replay:
        store.ingest(source_id)
    assert derivative.value.code == replay.value.code == "erasure_tombstone_fence"


def test_tombstone_contains_no_private_or_reversible_derivative() -> None:
    registry = build_default_registry()
    source_id = new_id()
    tombstone = SyntheticErasureStore(registry_version=registry.version).delete(
        source_id, revision=1
    )
    payload = tombstone.model_dump(mode="json")

    assert set(payload) == {
        "tombstone_id",
        "opaque_source_id",
        "registry_version",
        "deleted_at_revision",
        "fence_active",
    }
    with pytest.raises(ValidationError):
        ErasureTombstone.model_validate({**payload, "content_sha256": "0" * 64})


def test_all_private_classes_and_derivatives_cannot_influence_parameters() -> None:
    influences = tuple(
        ParameterInfluence(source_class=data_class, surface=surface, transformed=transformed)
        for data_class in tuple(DataClass)[1:]
        for surface in ParameterInfluenceSurface
        for transformed in (False, True)
    )

    decision = parameter_update_decision(influences)

    assert not decision.performed and decision.status == "private_influence_prohibited"
    assert set(decision.blocked_surfaces) == set(ParameterInfluenceSurface)


def test_registry_covers_migrations_001_through_006() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "ynoy" / "migrations"
    pattern = re.compile(r"CREATE TABLE IF NOT EXISTS ynoy\.([a-z0-9_]+)", re.IGNORECASE)
    discovered = {
        match.group(1)
        for path in sorted(root.glob("00[1-6]_*.sql"))
        for match in pattern.finditer(path.read_text(encoding="utf-8"))
    }

    assert discovered == set(MIGRATION_001_006_TABLES)
