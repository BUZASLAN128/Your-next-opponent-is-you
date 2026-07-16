from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, YnoyError
from ynoy.models import (
    AnnotationPresentation,
    PersonaAnnotationJudgment,
    PersonaModelProposal,
    PersonaProposalBundle,
    PersonaProposalPass,
    PersonaProposalRunReceipt,
    ReviewProviderEvidence,
    StudyArtifactIndex,
)
from ynoy.persona_study.artifacts import PersonaStudyStore
from ynoy.persona_study.assisted_attempts import (
    PROPOSALS_PATH as PROPOSALS_PATH,
)
from ynoy.persona_study.assisted_attempts import (
    ProposalAttempt,
    attempt_context,
    build_attempt_payloads,
)
from ynoy.persona_study.assisted_gates import (
    BASE_AUDIT_COUNT as BASE_AUDIT_COUNT,
)
from ynoy.persona_study.assisted_gates import (
    base_audit_ids as _base_audit_ids,
)
from ynoy.persona_study.assisted_gates import (
    oversized_guard as _oversized_guard,
)
from ynoy.persona_study.assisted_gates import (
    repeat_review_ids as _repeat_review_ids,
)
from ynoy.persona_study.assisted_review import (
    QUICK_REVIEW_PATH as QUICK_REVIEW_PATH,
)
from ynoy.persona_study.assisted_review import review_paths
from ynoy.persona_study.label_contract import (
    blind_map,
    presentations,
    validate_judgment_spans,
)
from ynoy.persona_study.local_proposer import ProposalPassName
from ynoy.util import canonical_sha256, sha256_text

REVIEW_BURDEN_CAP = 12


class PersonaProposer(Protocol):
    @property
    def provider_evidence(self) -> ReviewProviderEvidence: ...

    def propose(
        self,
        presentation: AnnotationPresentation,
        *,
        pass_name: ProposalPassName,
    ) -> PersonaAnnotationJudgment: ...


@dataclass(frozen=True, slots=True)
class AssistedLabelProposalResult:
    bundle: PersonaProposalBundle
    artifact_index: StudyArtifactIndex
    quick_review_path: Path | None


def propose_assisted_labels(
    store: PersonaStudyStore,
    study_id: str,
    proposer: PersonaProposer,
    *,
    attempt: ProposalAttempt = "primary",
) -> AssistedLabelProposalResult:
    index = store.read_index(study_id)
    proposal_path, previous_receipt = attempt_context(store, index, study_id, attempt)
    cards = presentations(store, study_id)
    provider = _provider_evidence(proposer)
    base_audit = _base_audit_ids(study_id, cards)
    pass_results = tuple(_propose_card(proposer, card) for card in cards)
    drafts = tuple(
        _proposal(card, direct, skeptical, False) for card, direct, skeptical in pass_results
    )
    repeat_review, repeat_disagreements = _repeat_review_ids(
        cards, blind_map(store, study_id), drafts
    )
    required = (
        base_audit
        | {
            card.presentation_id
            for card, direct, skeptical in pass_results
            if not _passes_stable(direct, skeptical)
        }
        | repeat_review
    )
    proposals = tuple(
        _proposal(card, direct, skeptical, card.presentation_id in required)
        for card, direct, skeptical in pass_results
    )
    receipt = _receipt(study_id, proposals, base_audit, provider, repeat_disagreements)
    bundle = PersonaProposalBundle(proposals=proposals, receipt=receipt)
    payloads = build_attempt_payloads(
        index, bundle, cards, proposal_path, attempt, previous_receipt
    )
    updated = store.append_artifacts(study_id, payloads)
    _, markdown_path = review_paths(attempt)
    review_path = (
        store.paths.artifact(study_id, markdown_path) if receipt.status == "review_ready" else None
    )
    return AssistedLabelProposalResult(bundle, updated, review_path)


PassResult = tuple[PersonaProposalPass | None, str | None]


def _propose_card(
    proposer: PersonaProposer, card: AnnotationPresentation
) -> tuple[AnnotationPresentation, PassResult, PassResult]:
    return card, _one_pass(proposer, card, "direct"), _one_pass(proposer, card, "skeptical")


def _one_pass(
    proposer: PersonaProposer,
    card: AnnotationPresentation,
    pass_name: ProposalPassName,
) -> PassResult:
    try:
        judgment = proposer.propose(card, pass_name=pass_name)
        safe = PersonaAnnotationJudgment.model_validate(judgment.model_dump(mode="python"))
        validate_judgment_spans(safe, card.focus.content)
        return PersonaProposalPass(pass_name=pass_name, judgment=safe), None
    except AdapterError as exc:
        if exc.code == "persona_proposer_input_too_large":
            return (
                PersonaProposalPass(
                    pass_name=pass_name,
                    method="deterministic_guard",
                    judgment=_oversized_guard(card.focus.content),
                ),
                "oversized_focus_guard",
            )
        return None, "invalid_output"
    except (YnoyError, ValidationError, AttributeError):
        return None, "invalid_output"


def _passes_stable(first: PassResult, second: PassResult) -> bool:
    return (
        first[0] is not None and second[0] is not None and first[0].judgment == second[0].judgment
    )


def _proposal(
    card: AnnotationPresentation,
    direct_result: PassResult,
    skeptical_result: PassResult,
    selected: bool,
) -> PersonaModelProposal:
    direct, direct_error = direct_result
    skeptical, skeptical_error = skeptical_result
    valid = tuple(item for item in (direct, skeptical) if item is not None)
    stable = _passes_stable(direct_result, skeptical_result)
    status = (
        "stable"
        if stable
        else "disagreement"
        if len(valid) == 2
        else "partial_invalid"
        if len(valid) == 1
        else "invalid"
    )
    reasons = _risk_reasons(valid[0].judgment if stable or len(valid) == 1 else None)
    if not stable:
        reasons.add("model_pass_unstable")
    for error in (direct_error, skeptical_error):
        if error:
            reasons.add(error)
    if direct_error == "invalid_output" or skeptical_error == "invalid_output":
        reasons.add("invalid_output")
    if selected:
        reasons.add("human_review_required")
    return PersonaModelProposal(
        presentation_id=card.presentation_id,
        order=card.order,
        focus_sha256=sha256_text(card.focus.content),
        direct=direct,
        skeptical=skeptical,
        chosen_judgment=valid[0].judgment if stable or len(valid) == 1 else None,
        status=cast(Any, status),
        risk_reasons=tuple(sorted(reasons)),
        selected_for_review=selected,
    )


def _risk_reasons(judgment: PersonaAnnotationJudgment | None) -> set[str]:
    if judgment is None:
        return set()
    reasons: set[str] = set()
    if judgment.confidence.value != "high":
        reasons.add("confidence_not_high")
    if judgment.should_abstain:
        reasons.add("model_abstained")
    if judgment.exclude_from_persona:
        reasons.add("model_excluded")
    if judgment.target_layer.value != "persona":
        reasons.add("non_persona_layer")
    return reasons


def _provider_evidence(proposer: PersonaProposer) -> ReviewProviderEvidence:
    try:
        return ReviewProviderEvidence.model_validate(
            proposer.provider_evidence.model_dump(mode="python")
        )
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "persona_proposer_identity_invalid",
            "The persona proposer did not provide valid pinned local identity.",
        ) from exc


def _receipt(
    study_id: str,
    proposals: tuple[PersonaModelProposal, ...],
    base_audit: set[str],
    provider: ReviewProviderEvidence,
    repeat_disagreements: int,
) -> PersonaProposalRunReceipt:
    required = sum(item.selected_for_review for item in proposals)
    payload = {
        "study_id": study_id,
        "status": "review_ready" if required <= REVIEW_BURDEN_CAP else "unreliable",
        "stable_count": sum(item.status == "stable" for item in proposals),
        "disagreement_count": sum(item.status == "disagreement" for item in proposals),
        "blind_repeat_disagreement_count": repeat_disagreements,
        "deterministic_guard_pass_count": sum(
            item.method == "deterministic_guard"
            for proposal in proposals
            for item in (proposal.direct, proposal.skeptical)
            if item is not None
        ),
        "invalid_pass_count": sum(item.direct is None for item in proposals)
        + sum(item.skeptical is None for item in proposals),
        "required_review_count": required,
        "proposal_set_sha256": canonical_sha256(
            [item.model_dump(mode="json") for item in proposals]
        ),
        "audit_selection_sha256": canonical_sha256(sorted(base_audit)),
        "provider_evidence": provider,
    }
    draft = cast(Any, PersonaProposalRunReceipt).model_construct(**payload, receipt_sha256="0" * 64)
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"receipt_sha256"}))
    return PersonaProposalRunReceipt.model_validate({**payload, "receipt_sha256": digest})
