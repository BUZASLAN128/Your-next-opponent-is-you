from __future__ import annotations

from test_persona_reaction_benchmark import _dataset

from ynoy.full_persona.reaction_split import build_reaction_split
from ynoy.models.full_persona import FullCorpusEvidence
from ynoy.util import canonical_sha256


def _reseal_evidence(item: FullCorpusEvidence, **updates: object) -> FullCorpusEvidence:
    payload = item.model_dump(mode="python") | updates
    payload.pop("evidence_sha256", None)
    payload["context"] = item.context
    draft = FullCorpusEvidence.model_construct(**payload, evidence_sha256="0" * 64)
    payload["evidence_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"evidence_sha256"})
    )
    return FullCorpusEvidence.model_validate(payload)


def test_split_rejects_exact_copy_from_cross_partition_membership() -> None:
    manifest, evidence = _dataset()
    changed = list(evidence)
    source = evidence[39]
    changed[20] = _reseal_evidence(
        changed[20],
        content=source.content,
        content_sha256=source.content_sha256,
        byte_length=len(source.content.encode()),
    )

    split = build_reaction_split(manifest, changed, sealed_count=24)
    duplicate_case_id = canonical_sha256(
        {"run_id": manifest.run_id, "evidence_id": changed[20].evidence_id}
    )
    assert duplicate_case_id not in {item.case_id for item in split.cases}


def test_split_excludes_source_neighbors_from_development_history() -> None:
    manifest, evidence = _dataset()
    neighbor = evidence[0]
    changed = list(evidence)
    changed[20] = _reseal_evidence(
        changed[20],
        source_key=neighbor.source_key,
        source_receipt=neighbor.source_receipt,
        blob_sha256=neighbor.blob_sha256,
    )

    split = build_reaction_split(manifest, changed, sealed_count=24)
    history_sources = {item.source_key for item in split.history}
    sealed_sources = {item.source_key for item in split.cases}
    assert history_sources.isdisjoint(sealed_sources)


def test_proxy_split_cannot_claim_prospective_user_label_support() -> None:
    manifest, evidence = _dataset()
    split = build_reaction_split(manifest, evidence, sealed_count=24)

    assert split.manifest.label_semantics == "lexical_proxy_not_user_validated"
    assert split.manifest.persona_identity_claimed is False
    assert split.manifest.semantic_adoption_claimed is False
    assert split.target_seal.targets_revealed is False
