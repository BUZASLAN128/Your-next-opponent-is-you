from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from support.persona_pack import built_pack, pack_atoms

from ynoy.full_persona.response_context import select_response_context
from ynoy.models.full_persona import EvidenceRole
from ynoy.models.full_persona_pack import (
    PersonaAtom,
    PersonaLayer,
    PersonaLayerView,
    PersonaPack,
    PersonaSupportRef,
)
from ynoy.util import canonical_sha256, sha256_text


def _direct_atom(pack: PersonaPack) -> PersonaAtom:
    return next(
        atom
        for atom in pack_atoms(pack)
        if atom.source_role == EvidenceRole.DIRECT
        and atom.support
        and atom.layer != PersonaLayer.TIMELINE
    )


def _support(base: PersonaAtom, claim: str, source_index: int) -> PersonaSupportRef:
    payload = base.support[0].model_dump(mode="json", exclude={"support_sha256"})
    payload.update(
        evidence_id=sha256_text(f"response-context-evidence-{source_index}"),
        evidence_sha256=sha256_text(f"response-context-evidence-payload-{source_index}"),
        source_key=sha256_text(f"response-context-source-{source_index}"),
        content_sha256=sha256_text(claim),
        byte_start=source_index * 10_000,
        byte_length=len(claim.encode("utf-8")),
        line_number=source_index + 1,
        char_start=0,
        char_end=len(claim),
        excerpt=claim,
        excerpt_sha256=sha256_text(claim),
    )
    return PersonaSupportRef.model_validate(
        {**payload, "support_sha256": canonical_sha256(payload)}
    )


def _atom(
    base: PersonaAtom,
    claim: str,
    semantic_key: str,
    source_index: int,
    observed_at: datetime,
) -> PersonaAtom:
    support = _support(base, claim, source_index)
    payload = base.model_dump(mode="python", exclude={"atom_id"})
    payload.update(
        semantic_key=semantic_key,
        claim=claim,
        support=(support,),
        evidence_ids=(support.evidence_id,),
        evidence_receipts=(support.support_sha256,),
        observation_count=1,
        first_observed_at=observed_at,
        last_observed_at=observed_at,
    )
    draft = PersonaAtom.model_construct(**payload, atom_id="0" * 64)
    normalized = draft.model_dump(mode="json", exclude={"atom_id"})
    return PersonaAtom.model_validate({**normalized, "atom_id": canonical_sha256(normalized)})


def _pack_with_atoms(pack: PersonaPack, atoms: tuple[PersonaAtom, ...]) -> PersonaPack:
    target_layer = atoms[0].layer
    layers: list[PersonaLayerView] = []
    for view in pack.layers:
        values = (*view.atoms, *atoms) if view.layer == target_layer else view.atoms
        layers.append(
            PersonaLayerView(
                layer=view.layer,
                atoms=tuple(sorted(values, key=lambda item: item.atom_id)),
                unknowns=view.unknowns,
            )
        )
    payload = pack.model_dump(mode="json", exclude={"pack_sha256"})
    payload["layers"] = [item.model_dump(mode="json") for item in layers]
    payload["retained_atom_count"] = sum(len(item.atoms) for item in layers)
    return PersonaPack.model_validate({**payload, "pack_sha256": canonical_sha256(payload)})


def test_context_dedupes_semantic_content_before_limit_and_keeps_diversity(
    tmp_path: Path,
) -> None:
    pack = built_pack(tmp_path)[3]
    base = _direct_atom(pack)
    duplicate_claim = "quasarcontext repeated evidence " + "alpha " * 120
    duplicate_key = sha256_text("quasarcontext-one-semantic-claim")
    duplicates = tuple(
        _atom(base, duplicate_claim, duplicate_key, index, datetime(2030, 1, 1, tzinfo=UTC))
        for index in range(10, 16)
    )
    diverse = tuple(
        _atom(
            base,
            f"quasarcontext diverse topic {index} " + f"detail{index} " * 90,
            sha256_text(f"quasarcontext-diverse-{index}"),
            index,
            datetime(2029, 1, 1, tzinfo=UTC),
        )
        for index in range(20, 25)
    )
    selected = select_response_context(
        _pack_with_atoms(pack, (*duplicates, *diverse)), "quasarcontext"
    )
    selected_ids = {item.atom_id for item in selected}
    by_id = {item.atom_id: item for item in (*duplicates, *diverse)}

    assert len({item.atom_id for item in duplicates}) == 6
    assert len({item.support[0].source_key for item in duplicates}) == 6
    assert len({by_id[item].semantic_key for item in selected_ids}) == 4
    assert len(selected_ids & {item.atom_id for item in duplicates}) == 1
    assert len(selected_ids & {item.atom_id for item in diverse}) == 3
    assert len(selected) == 4
    assert all(len(item.claim) <= 400 for item in selected)
    assert sum(len(item.claim) for item in selected) <= 1_600


def test_long_imported_expository_direct_text_is_not_response_context(
    tmp_path: Path,
) -> None:
    pack = built_pack(tmp_path)[3]
    base = _direct_atom(pack)
    claim = "importedexpository reference material " + "quoted explanation " * 120
    atom = _atom(
        base,
        claim,
        sha256_text("long-imported-expository-direct-text"),
        99,
        datetime(2030, 1, 1, tzinfo=UTC),
    )
    assert atom.source_role == EvidenceRole.DIRECT
    assert len(atom.claim) > 2_000
    assert select_response_context(_pack_with_atoms(pack, (atom,)), "importedexpository") == ()
