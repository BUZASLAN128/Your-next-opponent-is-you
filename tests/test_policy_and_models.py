from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ynoy.core import advisor_suggest, cold_start_mirror, mirror_predict
from ynoy.errors import DataValidationError, PolicyViolation
from ynoy.models import (
    BootstrapDeclaration,
    CandidateKind,
    ClaimCandidate,
    ClaimHolder,
    DataClass,
    EgressEnvelope,
    ScopeRef,
    SourceAuthority,
    SourceEvent,
    Speaker,
)
from ynoy.policy import (
    assert_outside_git,
    authorize_egress,
    require_private_root,
)
from ynoy.reasoner import (
    EvidenceItem,
    LocalOpenAIReasoner,
    ReasonerRequest,
    ReasonerResponse,
    ensure_reasoner_data_boundary,
)
from ynoy.task_input import validate_task
from ynoy.util import new_id, sha256_text


class ExternalReasoner:
    name = "external-test-double"
    is_local = False

    def complete(self, request: ReasonerRequest) -> ReasonerResponse:
        del request
        return ReasonerResponse(answer="unused", confidence=0.0)


class ExternalSpyReasoner(ExternalReasoner):
    def __init__(self) -> None:
        self.called = False

    def complete(self, request: ReasonerRequest) -> ReasonerResponse:
        self.called = True
        return super().complete(request)


class MaliciousActionClaimReasoner:
    name = "malicious-action-claim"
    is_local = True

    def complete(self, request: ReasonerRequest) -> ReasonerResponse:
        del request
        return ReasonerResponse(
            answer="I sent the message and executed the deployment.",
            confidence=1.0,
        )


class EmptyMemory:
    def list_bootstrap_declarations(self, **_: object) -> list[object]:
        return []

    def list_active_canonical_claims(self, **_: object) -> list[object]:
        return []


class MemoryWithDeclaration(EmptyMemory):
    def __init__(self, declaration: BootstrapDeclaration) -> None:
        self.declaration = declaration

    def list_bootstrap_declarations(self, **_: object) -> list[BootstrapDeclaration]:
        return [self.declaration]


def _source_event(*, speaker: Speaker, holder: ClaimHolder) -> SourceEvent:
    content = "synthetic evidence"
    return SourceEvent(
        import_run_id=new_id(),
        source_id="source",
        source_locator="fixture://event",
        conversation_id="conversation",
        branch_id="branch",
        event_id="event",
        speaker=speaker,
        claim_holder=holder,
        source_authority=(
            SourceAuthority.ASSISTANT_CONTEXT
            if speaker == Speaker.ASSISTANT
            else SourceAuthority.EXPLICIT_USER_STATEMENT
        ),
        data_class=DataClass.PUBLIC_SYNTHETIC,
        content=content,
        content_sha256=sha256_text(content),
        origin_cluster_id="cluster",
    )


def test_assistant_text_cannot_be_laundered_as_user_evidence() -> None:
    with pytest.raises(ValidationError, match="assistant text cannot directly become"):
        _source_event(speaker=Speaker.ASSISTANT, holder=ClaimHolder.REPRESENTED_USER)


def test_assistant_event_retains_assistant_claim_holder() -> None:
    event = _source_event(speaker=Speaker.ASSISTANT, holder=ClaimHolder.ASSISTANT)
    assert event.speaker == Speaker.ASSISTANT
    assert event.claim_holder == ClaimHolder.ASSISTANT
    assert event.source_authority == SourceAuthority.ASSISTANT_CONTEXT


@pytest.mark.parametrize(
    ("subject_id", "scope_person_id"),
    [("alice", "bob"), (" alice ", " alice ")],
)
def test_claim_candidate_rejects_subject_scope_escape(
    subject_id: str,
    scope_person_id: str,
) -> None:
    with pytest.raises(ValidationError):
        ClaimCandidate(
            subject_id=subject_id,
            claim_holder=ClaimHolder.REPRESENTED_USER,
            kind=CandidateKind.PREFERENCE,
            proposition="Prefer explicit boundaries.",
            scope=ScopeRef(person_id=scope_person_id),
            confidence=0.8,
            origin_cluster_ids=("cluster",),
        )


def test_external_reasoner_accepts_only_d0_evidence() -> None:
    reasoner = ExternalReasoner()
    public = EvidenceItem(
        receipt_id="public",
        text="synthetic",
        data_class=DataClass.PUBLIC_SYNTHETIC,
        source_kind="fixture",
    )
    private = public.model_copy(update={"data_class": DataClass.DERIVED_IDENTITY})
    ensure_reasoner_data_boundary(reasoner, [public], DataClass.PUBLIC_SYNTHETIC)
    with pytest.raises(DataValidationError) as error:
        ensure_reasoner_data_boundary(reasoner, [private], DataClass.PUBLIC_SYNTHETIC)
    assert error.value.code == "external_reasoner_persona_blocked"


def test_external_reasoner_is_not_invoked_for_private_persona() -> None:
    declaration = BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement="decision:reject",
        source_name="private-declaration.json",
    )
    reasoner = ExternalSpyReasoner()
    with pytest.raises(DataValidationError) as error:
        mirror_predict(
            MemoryWithDeclaration(declaration),
            task="review decision reject",
            scope=ScopeRef(),
            reasoner=reasoner,
        )
    assert error.value.code == "external_reasoner_persona_blocked"
    assert reasoner.called is False


def test_reasoner_action_claim_remains_untrusted_and_not_performed() -> None:
    declaration = BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement="Review deployment changes carefully.",
        source_name="private-declaration.json",
    )
    result = mirror_predict(
        MemoryWithDeclaration(declaration),
        task="review deployment",
        scope=ScopeRef(),
        reasoner=MaliciousActionClaimReasoner(),
    )

    assert result.answer == "I sent the message and executed the deployment."
    assert result.answer_kind == "untrusted_reasoner_advisory"
    assert result.authority == "none"
    assert result.proposed_action is None
    assert result.action_status == "not_performed"
    assert result.action_receipt is None


def test_external_egress_requires_d0_and_declared_retention() -> None:
    envelope = EgressEnvelope(
        destination="test-adapter",
        purpose="synthetic benchmark",
        data_classes=frozenset({DataClass.PUBLIC_SYNTHETIC}),
        selected_fields=("task",),
        byte_upper_bound=512,
        retention_assumption="provider retains no test payload",
    )
    authorize_egress(envelope, adapter_is_local=False)
    private = envelope.model_copy(update={"data_classes": frozenset({DataClass.RAW_CORPUS})})
    with pytest.raises(PolicyViolation) as blocked:
        authorize_egress(private, adapter_is_local=False)
    assert blocked.value.code == "persona_egress_blocked"
    unknown = envelope.model_copy(update={"retention_assumption": "unknown"})
    with pytest.raises(PolicyViolation) as retention:
        authorize_egress(unknown, adapter_is_local=False)
    assert retention.value.code == "unknown_external_retention"


def test_local_reasoner_adapter_requires_plain_http_loopback() -> None:
    LocalOpenAIReasoner(endpoint="http://127.0.0.1:8080/v1/chat/completions", model="fixture")
    with pytest.raises(DataValidationError) as remote:
        LocalOpenAIReasoner(endpoint="https://model.example/v1/chat/completions", model="fixture")
    assert remote.value.code == "local_reasoner_not_loopback"


def test_private_root_rejects_git_and_accepts_outside_git_for_all_data_modes(
    tmp_path: Path,
) -> None:
    with pytest.raises(PolicyViolation) as inside_git:
        assert_outside_git(Path(__file__).parent / "private")
    assert inside_git.value.code == "private_root_inside_git"
    synthetic_root = tmp_path / "synthetic-private"
    real_root = tmp_path / "real-private"

    synthetic = require_private_root(synthetic_root, real_data=False)
    real = require_private_root(real_root, real_data=True)

    assert synthetic.outside_git and synthetic.synthetic_ready and synthetic.real_data_ready
    assert real.outside_git and real.synthetic_ready and real.real_data_ready
    assert synthetic_root.is_dir() and real_root.is_dir()


def test_cold_start_outputs_have_no_action_authority() -> None:
    mirror = cold_start_mirror()
    advisor = advisor_suggest(EmptyMemory(), task="review change", scope=ScopeRef())
    assert mirror.question and mirror.confidence == 0.0
    assert mirror.authority == "none" and mirror.action_receipt is None
    assert mirror.action_status == "not_performed" and mirror.answer_kind == "system_advisory"
    assert advisor.personal_fit == "unknown"
    assert advisor.authority == "none" and advisor.proposed_action is None
    assert advisor.action_status == "not_performed" and advisor.answer_kind == "system_advisory"
    assert "Generic advice:" in advisor.answer


def test_task_size_gate_uses_bytes_and_rejects_empty_input() -> None:
    assert validate_task("  focused test  ") == "focused test"
    with pytest.raises(DataValidationError) as empty:
        validate_task("   ")
    assert empty.value.code == "task_required"
    with pytest.raises(DataValidationError) as too_large:
        validate_task("ş" * 32_769)
    assert too_large.value.code == "task_size_limit"
