from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from support.canonical_claims import confirmed_admission

from ynoy.bootstrap import load_bootstrap
from ynoy.constants import (
    DEFAULT_BOOTSTRAP_MAX_DECLARATIONS,
    DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES,
)
from ynoy.core import advisor_suggest, mirror_predict, select_evidence
from ynoy.errors import DataValidationError
from ynoy.models import (
    BootstrapDeclaration,
    CandidateKind,
    CandidateStatus,
    CanonicalClaim,
    DataClass,
    DecisionLabel,
    ScopeRef,
)
from ynoy.reasoner import DeterministicReasoner


@dataclass
class FakeMemory:
    declarations: list[BootstrapDeclaration] = field(default_factory=list)
    canonical_claims: list[CanonicalClaim] = field(default_factory=list)

    def list_bootstrap_declarations(
        self, *, subject_id: str = "self", include_inactive: bool = False
    ) -> list[BootstrapDeclaration]:
        del include_inactive
        return [item for item in self.declarations if item.subject_id == subject_id]

    def list_active_canonical_claims(
        self, *, subject_id: str = "self", evaluation_time: datetime
    ) -> list[CanonicalClaim]:
        del evaluation_time
        return [item for item in self.canonical_claims if item.subject_id == subject_id]


def test_zero_data_mirror_asks_one_high_value_question() -> None:
    result = mirror_predict(
        FakeMemory(),
        task="Should I accept this broad fallback?",
        scope=ScopeRef(project="pilot"),
        reasoner=DeterministicReasoner(),
    )
    assert result.confidence == 0.0
    assert result.personal_fit == "unknown"
    assert result.question is not None and result.question.count("?") == 1
    assert result.evidence_receipts == ()
    assert result.authority == "none" and result.action_receipt is None


def test_zero_data_advisor_is_generic_and_non_authoritative() -> None:
    result = advisor_suggest(
        FakeMemory(),
        task="How should I review this migration?",
        scope=ScopeRef(project="pilot"),
        reasoner=DeterministicReasoner(),
    )
    assert result.answer.startswith("Generic advice:")
    assert result.personal_fit == "unknown"
    assert result.unknowns == ("personal_fit",)
    assert result.authority == "none"
    assert result.proposed_action is None and result.action_receipt is None


def test_scope_and_stale_rules_are_excluded_and_disclosed() -> None:
    expired = datetime.now(UTC) - timedelta(days=1)
    memory = FakeMemory(
        declarations=[
            BootstrapDeclaration(
                kind=CandidateKind.PREFERENCE,
                statement="tenant decision:reject",
                scope=ScopeRef(project="other"),
                source_name="fixture.json",
                data_class=DataClass.PUBLIC_SYNTHETIC,
                synthetic=True,
            ),
            BootstrapDeclaration(
                kind=CandidateKind.PREFERENCE,
                statement="tenant decision:accept",
                scope=ScopeRef(project="pilot", valid_until=expired),
                source_name="fixture.json",
                data_class=DataClass.PUBLIC_SYNTHETIC,
                synthetic=True,
            ),
        ]
    )
    result = mirror_predict(
        memory,
        task="tenant change",
        scope=ScopeRef(project="pilot"),
        reasoner=DeterministicReasoner(),
    )
    assert "available_evidence_belongs_to_another_scope" in result.unknowns
    assert "stale_evidence_was_excluded" in result.unknowns
    assert result.evidence_receipts == ()


def test_same_scope_lexically_unrelated_persona_abstains_without_receipts() -> None:
    declaration = BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement="Prefer deterministic rollback procedures.",
        scope=ScopeRef(project="pilot"),
        source_name="fixture.json",
        data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )
    result = mirror_predict(
        FakeMemory(declarations=[declaration]),
        task="Assess interface color contrast",
        scope=ScopeRef(project="pilot"),
        reasoner=DeterministicReasoner(),
    )

    assert result.evidence_receipts == ()
    assert result.confidence == 0.0
    assert result.personal_fit == "unknown"
    assert result.question is not None


def test_select_evidence_ignores_inactive_canonical_claim() -> None:
    _, _, admission = confirmed_admission()
    inactive = admission.claim.model_copy(update={"status": CandidateStatus.INVALIDATED})
    selected = select_evidence(
        FakeMemory(canonical_claims=[inactive]),
        task="evidence rollback",
        scope=ScopeRef(project="synthetic-canonical"),
    )
    assert selected.items == ()


def test_synthetic_bootstrap_is_explicit_and_idempotently_identified(tmp_path: Path) -> None:
    source = tmp_path / "bootstrap.json"
    source.write_text(
        json.dumps(
            [
                {
                    "kind": "preference",
                    "statement": "Reject hidden tenant fallbacks.",
                    "decision_label": "reject",
                    "synthetic": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    first = load_bootstrap(source, synthetic=True)
    second = load_bootstrap(source, synthetic=True)
    assert [item.record_id for item in first] == [item.record_id for item in second]
    assert first[0].status == CandidateStatus.CONFIRMED
    assert first[0].data_class == DataClass.PUBLIC_SYNTHETIC
    assert first[0].decision_label == DecisionLabel.REJECT


def test_bootstrap_file_uses_one_source_record_for_all_declarations(tmp_path: Path) -> None:
    source = tmp_path / "multi-bootstrap.json"
    source.write_text(
        json.dumps(
            [
                {"statement": "First explicit rule.", "synthetic": True},
                {"statement": "Second explicit rule.", "synthetic": True},
            ]
        ),
        encoding="utf-8",
    )
    declarations = load_bootstrap(source, synthetic=True)
    assert len(declarations) == 2
    assert len({item.record_id for item in declarations}) == 2
    assert len({item.source_record_id for item in declarations}) == 1


def test_synthetic_bootstrap_requires_per_record_marker(tmp_path: Path) -> None:
    source = tmp_path / "bootstrap.json"
    source.write_text('[{"statement":"not marked"}]', encoding="utf-8")
    with pytest.raises(DataValidationError) as error:
        load_bootstrap(source, synthetic=True)
    assert error.value.code == "synthetic_fixture_marker_required"


def test_real_bootstrap_persistence_is_blocked_for_json_and_markdown(tmp_path: Path) -> None:
    payload = {
        "statement": "Prefer reversible changes.",
        "speaker": "user",
        "claim_holder": "represented_user",
        "source_authority": "explicit_user_statement",
        "adopted": True,
        "evidence_plane": "identity_interpretation",
        "synthetic": False,
    }
    source = tmp_path / "bootstrap.json"
    source.write_text(json.dumps([payload]), encoding="utf-8")
    with pytest.raises(DataValidationError) as blocked:
        load_bootstrap(source)
    assert blocked.value.code == "real_identity_persistence_unsupported"

    markdown = tmp_path / "bootstrap.md"
    markdown.write_text("# Explicit\n- Prefer reversible changes.\n", encoding="utf-8")
    with pytest.raises(DataValidationError) as blocked:
        load_bootstrap(markdown)
    assert blocked.value.code == "real_identity_persistence_unsupported"


def test_bootstrap_source_stat_limit_precedes_open_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "oversized.json"
    source.write_bytes(b"[{}]")
    opened = hashed = False

    def fail_open(*_: object, **__: object):
        nonlocal opened
        opened = True
        raise AssertionError("oversized bootstrap must not be opened")

    def fail_hash(_: bytes) -> str:
        nonlocal hashed
        hashed = True
        raise AssertionError("oversized bootstrap must not be hashed")

    monkeypatch.setattr("ynoy.bootstrap.DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES", 3)
    monkeypatch.setattr("ynoy.bootstrap.sha256_bytes", fail_hash)
    monkeypatch.setattr(Path, "open", fail_open)
    with pytest.raises(DataValidationError) as error:
        load_bootstrap(source, synthetic=True)
    assert error.value.code == "bootstrap_source_too_large"
    assert opened is False and hashed is False


def test_bootstrap_read_growth_guard_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "growing.json"
    source.write_bytes(b"[]")
    monkeypatch.setattr("ynoy.bootstrap.DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES", 8)
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: BytesIO(b"0" * 9))
    with pytest.raises(DataValidationError) as error:
        load_bootstrap(source, synthetic=True)
    assert error.value.code == "bootstrap_source_too_large"


def test_bootstrap_rejects_statement_over_byte_limit(tmp_path: Path) -> None:
    source = tmp_path / "large-statement.json"
    statement = "ş" * (DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES // 2 + 1)
    source.write_text(
        json.dumps([{"statement": statement, "synthetic": True}], ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError) as error:
        load_bootstrap(source, synthetic=True)
    assert error.value.code == "bootstrap_statement_too_large"


def test_bootstrap_rejects_excess_declaration_count(tmp_path: Path) -> None:
    source = tmp_path / "too-many-declarations.json"
    declarations = [
        {"statement": f"synthetic rule {index}", "synthetic": True}
        for index in range(DEFAULT_BOOTSTRAP_MAX_DECLARATIONS + 1)
    ]
    source.write_text(json.dumps(declarations), encoding="utf-8")
    with pytest.raises(DataValidationError) as error:
        load_bootstrap(source, synthetic=True)
    assert error.value.code == "bootstrap_declaration_limit"
