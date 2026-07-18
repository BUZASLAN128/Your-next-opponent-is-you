from __future__ import annotations

from collections.abc import Mapping

from ynoy.decision_conflict import DecisionResolution
from ynoy.models import DecisionLabel, Mode, OutputEnvelope
from ynoy.models.formal_decision import (
    AbstentionJudgment,
    AdmittedDecisionClaim,
    DecisionGroupKey,
    ExplicitPolicyJudgment,
    GenericAdvisorJudgment,
    InferredPersonaJudgment,
    MirrorCandidate,
    PublicJudgment,
)
from ynoy.models.formal_evaluation import CalibrationProfile
from ynoy.models.review_vocab import TargetLayer

_POLICY_LAYERS = {
    TargetLayer.PROJECT_CONSTITUTION,
    TargetLayer.PROTECTED_CONTROL,
    TargetLayer.SCOPED_POLICY,
}


def choose_mirror_candidate(
    scores: Mapping[DecisionLabel, float],
    *,
    full_target: DecisionGroupKey,
    predictor_version: str,
    extractor_version: str,
    feature_schema_version: str,
    stratum: str,
    tie_order: tuple[DecisionLabel, ...],
) -> MirrorCandidate:
    """Choose one internal candidate with a frozen, label-blind tie rule."""
    if not scores or set(scores) != set(tie_order) or len(set(tie_order)) != len(tie_order):
        raise ValueError("candidate labels and frozen tie order must match exactly")
    best = max(scores.values())
    predicted = next(label for label in tie_order if scores[label] == best)
    return MirrorCandidate(
        full_target=full_target,
        predicted_label=predicted,
        ranking_score=best,
        predictor_version=predictor_version,
        extractor_version=extractor_version,
        feature_schema_version=feature_schema_version,
        stratum=stratum,
    )


def resolve_public_judgment(
    *,
    mode: Mode,
    resolution: DecisionResolution,
    candidate: MirrorCandidate | None = None,
    calibration_profile: CalibrationProfile | None = None,
    requested_output: str = "coding_judgment",
) -> PublicJudgment:
    """Apply deterministic basis precedence; models cannot construct public output."""
    if not resolution.safe:
        return _abstain(mode, resolution.reasons)
    policies = tuple(
        item
        for item in resolution.active_claims
        if item.claim.target_layer in _POLICY_LAYERS and item.claim.decision_label is not None
    )
    if len(policies) == 1:
        policy = policies[0]
        label = policy.claim.decision_label
        assert label is not None
        return ExplicitPolicyJudgment(
            decision_label=label,
            claim_ids=(policy.claim.record_id,),
        )
    if len(policies) > 1:
        return _abstain(mode, ("ambiguous_explicit_policy",))
    if mode == Mode.ADVISOR:
        return GenericAdvisorJudgment()
    if candidate is None or calibration_profile is None:
        return _abstain(mode, ("persona_not_calibrated",))
    probability = _calibrated_probability(candidate, calibration_profile, requested_output)
    if probability is None or probability < calibration_profile.persona_threshold:
        return _abstain(mode, ("persona_calibration_gate_failed",))
    evidence = _persona_evidence(resolution.active_claims, candidate)
    if not evidence:
        return _abstain(mode, ("persona_evidence_missing",))
    return InferredPersonaJudgment(
        decision_label=candidate.predicted_label,
        calibrated_probability=probability,
        calibration_profile_sha256=calibration_profile.profile_sha256,
        claim_ids=tuple(item.claim.record_id for item in evidence),
    )


def judgment_to_output(judgment: PublicJudgment) -> OutputEnvelope:
    """Project the disjoint judgment union into the stable CLI envelope."""
    if isinstance(judgment, ExplicitPolicyJudgment):
        return OutputEnvelope(
            mode=judgment.mode,
            answer=f"Applicable explicit policy: {judgment.decision_label.value}.",
            confidence=None,
            evidence_receipts=tuple(str(item) for item in judgment.claim_ids),
            personal_fit="unknown",
            judgment_basis=judgment.basis,
        )
    if isinstance(judgment, InferredPersonaJudgment):
        return OutputEnvelope(
            mode=judgment.mode,
            answer=f"Predicted decision: {judgment.decision_label.value}.",
            confidence=judgment.calibrated_probability,
            evidence_receipts=tuple(str(item) for item in judgment.claim_ids),
            personal_fit="known",
            judgment_basis=judgment.basis,
        )
    if isinstance(judgment, GenericAdvisorJudgment):
        return OutputEnvelope(
            mode=judgment.mode,
            answer=(
                "Generic advice: define the expected behavior, choose a reversible option, "
                "and verify the result before expanding scope."
            ),
            confidence=None,
            unknowns=("personal_fit",),
            personal_fit="unknown",
            judgment_basis=judgment.basis,
        )
    return OutputEnvelope(
        mode=judgment.mode,
        answer="I cannot make a personal prediction from the available evidence.",
        confidence=None,
        unknowns=judgment.unknowns,
        personal_fit="unknown",
        judgment_basis=judgment.basis,
    )


def _calibrated_probability(
    candidate: MirrorCandidate,
    profile: CalibrationProfile,
    requested_output: str,
) -> float | None:
    exact = (
        profile.requested_output == requested_output
        and profile.full_decision_target == candidate.full_target
        and profile.represented_user_outcome == candidate.predicted_label.value
        and profile.predictor_version == candidate.predictor_version
        and profile.extractor_version == candidate.extractor_version
        and profile.feature_schema_version == candidate.feature_schema_version
        and candidate.stratum in profile.strata
    )
    return profile.probability_for(candidate.ranking_score) if exact else None


def _persona_evidence(
    claims: tuple[AdmittedDecisionClaim, ...], candidate: MirrorCandidate
) -> tuple[AdmittedDecisionClaim, ...]:
    return tuple(
        item
        for item in claims
        if item.identity.full_key == candidate.full_target
        and item.claim.target_layer == TargetLayer.PERSONA_CANDIDATE
    )


def _abstain(mode: Mode, reasons: tuple[str, ...]) -> AbstentionJudgment:
    values = reasons or ("basis_unavailable",)
    return AbstentionJudgment(mode=mode, reason=values[0], unknowns=values)
