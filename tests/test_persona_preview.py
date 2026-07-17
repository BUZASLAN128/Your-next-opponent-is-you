from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import synthetic_audit
from support.canonical_claims import confirmed_admission

from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.models import (
    CandidateKind,
    CandidateStatus,
    DataClass,
    EvidenceRegime,
    PersonaFacet,
    PersonaStratum,
    PersonaViewName,
    SourceAuthority,
    TargetLayer,
)
from ynoy.persona import build_persona_preview
from ynoy.storage import CanonicalClaimRepository, Database

STRATA = (
    (PersonaStratum.DECISIONS_AND_POLICY, CandidateKind.PREFERENCE),
    (PersonaStratum.VALUES_AND_BELIEFS, CandidateKind.VALUE),
    (PersonaStratum.GOALS_AND_CONTINUITY, CandidateKind.GOAL),
    (PersonaStratum.COMMUNICATION_AND_METACOGNITION, CandidateKind.METACOGNITION),
    (PersonaStratum.SKILLS_NARRATIVE_AND_RELATIONSHIPS, CandidateKind.SKILL),
)


def _persona_claim(index: int, stratum: PersonaStratum, kind: CandidateKind):
    return confirmed_admission(
        offset=index,
        target_layer=TargetLayer.PERSONA_CANDIDATE,
        persona_kind=kind,
        persona_stratum=stratum,
    )[2].claim


def test_preview_has_five_strata_and_is_input_order_independent() -> None:
    claims = tuple(
        _persona_claim(index, stratum, kind)
        for index, (stratum, kind) in enumerate(STRATA, start=1)
    )

    forward = build_persona_preview(claims)
    reverse = build_persona_preview(tuple(reversed(claims)))

    assert forward == reverse
    assert tuple(view.name for view in forward.views) == tuple(PersonaViewName)
    assert tuple(view.facets[0].stratum for view in forward.views) == tuple(
        item[0] for item in STRATA
    )
    assert forward.claim_count == 5
    assert forward.missing_views == ()


def test_preview_preserves_canonical_admission_links_without_summary() -> None:
    claim = _persona_claim(101, *STRATA[0])
    preview = build_persona_preview((claim,))
    facet = preview.views[0].facets[0]

    assert facet.statement == claim.literal_statement
    assert facet.scope == claim.scope
    assert facet.record_id == claim.record_id
    assert facet.admission_receipt_id == claim.admission_receipt_id
    assert facet.source_link_ids == claim.source_link_ids
    assert preview.admission_receipts == (claim.admission_receipt_id,)
    assert preview.source_link_ids == claim.source_link_ids
    assert '"summary"' not in json.dumps(preview.model_dump(mode="json"))


def test_operating_memory_remains_system_control_and_never_a_facet() -> None:
    preview = build_persona_preview((_persona_claim(201, *STRATA[3]),))
    facets = tuple(facet for view in preview.views for facet in view.facets)
    memory = preview.operating_memory

    assert memory.evidence_regime == EvidenceRegime.ZERO
    assert memory.persona_evidence_count == 0
    assert all(not isinstance(rule, PersonaFacet) for rule in memory.rules)
    assert all(rule.source_authority == SourceAuthority.SYSTEM_CONTROL for rule in memory.rules)
    assert all(
        facet.source_authority == SourceAuthority.EXPLICIT_USER_STATEMENT for facet in facets
    )


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("empty", "canonical_persona_claims_required"),
        ("noncanonical", "canonical_persona_claim_required"),
        ("nonpersona", "canonical_persona_claim_inactive"),
        ("inactive", "canonical_persona_claim_inactive"),
        ("mixed_subject", "persona_subject_mismatch"),
        ("duplicate", "persona_duplicate_claim"),
    ],
)
def test_preview_rejects_noncanonical_or_inactive_sets(case: str, error_code: str) -> None:
    first = _persona_claim(301, *STRATA[0])
    second = _persona_claim(302, *STRATA[1])
    if case == "empty":
        claims: tuple[object, ...] = ()
    elif case == "noncanonical":
        claims = (object(),)
    elif case == "nonpersona":
        claims = (confirmed_admission(offset=303)[2].claim,)
    elif case == "inactive":
        claims = (
            first.model_copy(
                update={"status": CandidateStatus.SUPERSEDED, "superseded_by": uuid4()}
            ),
        )
    elif case == "mixed_subject":
        claims = (first, second.model_copy(update={"subject_id": "someone-else"}))
    else:
        claims = (first, first)

    with pytest.raises(DataValidationError) as blocked:
        build_persona_preview(claims)  # type: ignore[arg-type]
    assert blocked.value.code == error_code


def _run_cli(
    arguments: Sequence[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    exit_code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return exit_code, payload


@pytest.mark.integration
def test_persona_cli_reads_only_active_canonical_claims(
    test_database: Database,
    test_database_url: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    offset = uuid4().int % 1_000_000 + 2_000_000
    subject_id = f"persona-preview-{uuid4()}"
    admission = confirmed_admission(
        offset=offset,
        subject_id=subject_id,
        target_layer=TargetLayer.PERSONA_CANDIDATE,
        persona_kind=CandidateKind.VALUE,
        persona_stratum=PersonaStratum.VALUES_AND_BELIEFS,
    )[2]
    CanonicalClaimRepository(test_database, data_class=DataClass.PUBLIC_SYNTHETIC).admit(
        admission, synthetic_audit(artifact_id=str(admission.claim.record_id))
    )

    exit_code, payload = _run_cli(
        [
            "--private-root",
            str(tmp_path),
            "--database-url",
            test_database_url,
            "persona",
            "preview",
            "--subject-id",
            subject_id,
            "--synthetic",
        ],
        capsys,
    )

    assert exit_code == 0 and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    assert result["persona_state"] == "canonical_admitted"
    assert result["database_used"] is True and result["provider_used"] is False
    assert result["persistence_status"] == "canonical_claims"
    assert result["claim_count"] == 1
    assert result["automatic_core_promotion"] is False
