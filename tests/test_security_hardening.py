from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest
from pydantic import ValidationError

from ynoy.cli.handlers.common import reasoner_from_args
from ynoy.cli.handlers.corpus import _ingest, _inventory
from ynoy.config import Settings
from ynoy.core import mirror_predict
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import (
    BootstrapDeclaration,
    CandidateKind,
    ClaimHolder,
    DataClass,
    DecisionLabel,
    ScopeRef,
    SourceAuthority,
    SourceEvent,
    Speaker,
)
from ynoy.reasoner import LocalOpenAIReasoner, ReasonerRequest, ReasonerResponse
from ynoy.util import new_id, sha256_text


class DeclarationMemory:
    def __init__(self, declaration: BootstrapDeclaration) -> None:
        self.declaration = declaration

    def list_bootstrap_declarations(self, **_: object) -> list[BootstrapDeclaration]:
        return [self.declaration]

    def list_active_canonical_claims(self, **_: object) -> list[object]:
        return []


class UntouchedContext:
    def __init__(self) -> None:
        self.accessed = False

    def artifacts(self, **_: object):
        self.accessed = True
        raise AssertionError("Git source must be rejected before artifact access")

    def database(self, **_: object):
        self.accessed = True
        raise AssertionError("Git source must be rejected before database access")


def _settings(*, attested: bool) -> Settings:
    return Settings(
        private_root=None,
        postgres_data_path=None,
        database_url=None,
        local_reasoner_url="http://127.0.0.1:8080/v1/chat/completions",
        local_model_attested=attested,
        local_reasoner_model="fixture-model",
        embedding_model="fixture-embedding",
    )


def _pasted_user_turn(holder: ClaimHolder) -> SourceEvent:
    content = "Pasted from Alice: I always approve broad production fallbacks."
    return SourceEvent(
        import_run_id=new_id(),
        source_id="synthetic-source",
        source_locator="fixture://pasted-turn",
        conversation_id="conversation",
        branch_id="branch",
        event_id="event",
        speaker=Speaker.USER,
        claim_holder=holder,
        source_authority=SourceAuthority.USER_TURN_UNATTRIBUTED,
        data_class=DataClass.PUBLIC_SYNTHETIC,
        content=content,
        content_sha256=sha256_text(content),
        origin_cluster_id="cluster",
    )


def test_pasted_user_turn_stays_unattributed_and_cannot_adopt_third_party_claim() -> None:
    event = _pasted_user_turn(ClaimHolder.UNKNOWN)
    assert event.source_authority == SourceAuthority.USER_TURN_UNATTRIBUTED
    assert event.claim_holder == ClaimHolder.UNKNOWN
    with pytest.raises(ValidationError, match="unreviewed user turns cannot claim"):
        _pasted_user_turn(ClaimHolder.REPRESENTED_USER)


def test_loopback_reasoner_needs_attestation_before_receiving_d3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[ReasonerRequest] = []

    def complete(_: LocalOpenAIReasoner, request: ReasonerRequest) -> ReasonerResponse:
        calls.append(request)
        return ReasonerResponse(
            answer="Predicted decision: reject.",
            predicted_label=DecisionLabel.REJECT,
            confidence=0.8,
        )

    monkeypatch.setattr(LocalOpenAIReasoner, "complete", complete)
    declaration = BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement="review decision:reject",
        source_name="private-declaration.json",
    )
    args = Namespace(reasoner="local")
    untrusted = reasoner_from_args(args, _settings(attested=False))
    with pytest.raises(DataValidationError) as blocked:
        mirror_predict(
            DeclarationMemory(declaration), task="review", scope=ScopeRef(), reasoner=untrusted
        )
    assert blocked.value.code == "external_reasoner_persona_blocked"
    assert calls == []
    trusted = reasoner_from_args(args, _settings(attested=True))
    result = mirror_predict(
        DeclarationMemory(declaration), task="review", scope=ScopeRef(), reasoner=trusted
    )
    assert result.personal_fit == "unknown"
    assert result.confidence is None
    assert result.judgment_basis.value == "abstention"
    assert len(calls) == 1


@pytest.mark.parametrize("handler", [_inventory, _ingest])
def test_real_corpus_inside_git_is_blocked_before_inventory_or_ingest(handler) -> None:
    context = UntouchedContext()
    args = Namespace(
        synthetic=False,
        archive=str(Path(__file__).resolve()),
        markdown_report=False,
    )
    with pytest.raises(PolicyViolation) as error:
        handler(args, context)
    assert error.value.code == "private_root_inside_git"
    assert context.accessed is False
