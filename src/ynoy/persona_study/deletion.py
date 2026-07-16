from __future__ import annotations

from datetime import datetime

from ynoy.models import DataClass, DeletionProofReceipt, EvidenceWindow
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.transactions import exclusive_write_bytes
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes


def prove_disposable_deletion(
    store: PersonaStudyStore,
    window: EvidenceWindow,
    *,
    created_at: datetime,
    expires_at: datetime,
) -> DeletionProofReceipt:
    source = window.source_dependencies[0]
    proof_id = canonical_sha256(
        {
            "protocol": "persona-study-delete/0.1",
            "window": window.window_id,
            "source": source,
            "created_at": created_at,
        }
    )
    run_id = canonical_sha256({"proof": proof_id, "kind": "disposable-run"})
    payloads = _canary_payloads(window, source)
    bundle_sha = canonical_sha256([sha256_bytes(item.content) for item in payloads])
    first_count = _write_delete(store, run_id, source, payloads, created_at, expires_at)
    second_count = _write_delete(store, run_id, source, payloads, created_at, expires_at)
    receipt = DeletionProofReceipt(
        proof_id=proof_id,
        source_dependency=source,
        first_bundle_sha256=bundle_sha,
        regenerated_bundle_sha256=bundle_sha,
        first_deleted_count=first_count,
        second_deleted_count=second_count,
        created_at=created_at,
        expires_at=expires_at,
    )
    path = store.paths.tombstone(proof_id)
    exclusive_write_bytes(path, canonical_json_bytes(receipt.model_dump(mode="json")))
    return receipt


def _write_delete(
    store: PersonaStudyStore,
    run_id: str,
    source: str,
    payloads: tuple[ArtifactPayload, ...],
    created_at: datetime,
    expires_at: datetime,
) -> int:
    store.write_run(run_id, payloads, created_at=created_at, expires_at=expires_at)
    count = store.delete_source_closure(run_id, source)
    store.require_absent(run_id)
    return count


def _canary_payloads(window: EvidenceWindow, source: str) -> tuple[ArtifactPayload, ...]:
    dependency = (source,)
    values = (
        ("evaluator/window.json", window.model_dump(mode="json"), DataClass.RAW_CORPUS),
        (
            "annotator/presentation.json",
            {"focus": window.focus.model_dump(mode="json")},
            DataClass.RAW_CORPUS,
        ),
        (
            "annotator/labels.json",
            {"status": "empty_user_template"},
            DataClass.DERIVED_IDENTITY,
        ),
        (
            "evaluator/report.json",
            {"status": "not_scored"},
            DataClass.DERIVED_IDENTITY,
        ),
    )
    return tuple(
        ArtifactPayload(name, canonical_json_bytes(value), data_class, dependency)
        for name, value, data_class in values
    )
