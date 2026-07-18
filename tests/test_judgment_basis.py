from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from support.formal_decisions import admitted_claim

from ynoy.decision_conflict import DecisionResolution
from ynoy.judgment import choose_mirror_candidate, judgment_to_output, resolve_public_judgment
from ynoy.models import DecisionLabel, Mode, TargetLayer
from ynoy.models.formal_decision import (
    AbstentionJudgment,
    GenericAdvisorJudgment,
    InferredPersonaJudgment,
    JudgmentBasis,
    PublicJudgment,
)
from ynoy.models.formal_evaluation import CalibrationBin, CalibrationProfile
from ynoy.util import canonical_sha256


def _resolution(*claims) -> DecisionResolution:
    return DecisionResolution(tuple(claims), (), ())


def _candidate(claim, score: float = 0.99):
    return choose_mirror_candidate(
        {DecisionLabel.ACCEPT: score, DecisionLabel.REJECT: 0.1},
        full_target=claim.identity.full_key,
        predictor_version="predictor/1",
        extractor_version="extractor/1",
        feature_schema_version="features/1",
        stratum="chronological_future",
        tie_order=(DecisionLabel.REJECT, DecisionLabel.ACCEPT),
    )


def _profile(claim, **updates) -> CalibrationProfile:
    payload = {
        "requested_output": "coding_judgment",
        "full_decision_target": claim.identity.full_key,
        "represented_user_outcome": "accept",
        "basis": "inferredPersona",
        "predictor_version": "predictor/1",
        "extractor_version": "extractor/1",
        "feature_schema_version": "features/1",
        "mapping_version": "mapping/1",
        "strata": ("chronological_future",),
        "fit_case_ids": ("fit-1",),
        "validation_case_ids": ("validation-1",),
        "sealed_case_ids": ("sealed-1",),
        "bins": (
            CalibrationBin(
                lower_score=0.9,
                upper_score=1.0,
                calibrated_probability=0.8,
            ),
        ),
        "persona_threshold": 0.75,
        "freeze_receipt_sha256": "d" * 64,
        **updates,
    }
    draft = CalibrationProfile.model_construct(**payload, profile_sha256="0" * 64)
    digest = canonical_sha256(draft.model_dump(mode="json", exclude={"profile_sha256"}))
    return CalibrationProfile.model_validate(
        {**draft.model_dump(mode="python"), "profile_sha256": digest}
    )


def test_uncalibrated_model_score_cannot_emit_persona() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)

    judgment = resolve_public_judgment(
        mode=Mode.MIRROR,
        resolution=_resolution(claim),
        candidate=_candidate(claim),
    )

    assert isinstance(judgment, AbstentionJudgment)
    assert judgment.reason == "persona_not_calibrated"


def test_persona_calibration_profile_is_frozen_and_target_exact() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)
    candidate = _candidate(claim)
    wrong = _profile(claim, requested_output="another_output")

    judgment = resolve_public_judgment(
        mode=Mode.MIRROR,
        resolution=_resolution(claim),
        candidate=candidate,
        calibration_profile=wrong,
    )

    assert isinstance(judgment, AbstentionJudgment)
    assert judgment.reason == "persona_calibration_gate_failed"


def test_sealed_labels_cannot_influence_calibration_profile_or_threshold() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)
    draft = _profile(claim).model_copy(
        update={"validation_case_ids": ("sealed-1",), "profile_sha256": "0" * 64}
    )
    payload = draft.model_dump(mode="python")
    payload["profile_sha256"] = canonical_sha256(
        draft.model_dump(mode="json", exclude={"profile_sha256"})
    )

    try:
        CalibrationProfile.model_validate(payload)
    except ValidationError as error:
        assert "partitions must be disjoint" in str(error)
    else:
        raise AssertionError("sealed cases cannot enter calibration partitions")


def test_explicit_policy_does_not_require_persona_calibration() -> None:
    policy = admitted_claim(decision_label=DecisionLabel.REJECT)

    judgment = resolve_public_judgment(mode=Mode.MIRROR, resolution=_resolution(policy))

    assert judgment.basis == JudgmentBasis.EXPLICIT_POLICY
    assert judgment.decision_label == DecisionLabel.REJECT


def test_generic_advisor_remains_nonpersonal_at_cold_start() -> None:
    judgment = resolve_public_judgment(
        mode=Mode.ADVISOR,
        resolution=_resolution(),
    )
    output = judgment_to_output(judgment)

    assert isinstance(judgment, GenericAdvisorJudgment)
    assert output.judgment_basis == JudgmentBasis.GENERIC_ADVISOR
    assert output.confidence is None and output.personal_fit == "unknown"


def test_internal_mirror_candidate_is_not_a_public_output_type() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)

    with pytest.raises(ValidationError):
        TypeAdapter(PublicJudgment).validate_python(_candidate(claim).model_dump(mode="python"))


def test_mirror_argmax_cannot_bypass_basis_gate() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)
    profile = _profile(claim, persona_threshold=0.9)

    judgment = resolve_public_judgment(
        mode=Mode.MIRROR,
        resolution=_resolution(claim),
        candidate=_candidate(claim),
        calibration_profile=profile,
    )

    assert isinstance(judgment, AbstentionJudgment)


def test_mirror_argmax_tie_uses_frozen_label_blind_order() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)
    args = {
        "full_target": claim.identity.full_key,
        "predictor_version": "predictor/1",
        "extractor_version": "extractor/1",
        "feature_schema_version": "features/1",
        "stratum": "chronological_future",
        "tie_order": (DecisionLabel.REJECT, DecisionLabel.ACCEPT),
    }

    first = choose_mirror_candidate({DecisionLabel.ACCEPT: 0.8, DecisionLabel.REJECT: 0.8}, **args)
    second = choose_mirror_candidate({DecisionLabel.REJECT: 0.8, DecisionLabel.ACCEPT: 0.8}, **args)

    assert first == second and first.predicted_label == DecisionLabel.REJECT


def test_calibrated_persona_probability_is_the_only_persona_confidence() -> None:
    claim = admitted_claim(target_layer=TargetLayer.PERSONA_CANDIDATE)
    judgment = resolve_public_judgment(
        mode=Mode.MIRROR,
        resolution=_resolution(claim),
        candidate=_candidate(claim),
        calibration_profile=_profile(claim),
    )
    output = judgment_to_output(judgment)

    assert isinstance(judgment, InferredPersonaJudgment)
    assert output.confidence == 0.8
    assert output.judgment_basis == JudgmentBasis.INFERRED_PERSONA
