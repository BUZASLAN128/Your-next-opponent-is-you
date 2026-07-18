from __future__ import annotations

from datetime import datetime
from uuid import UUID

from support.canonical_claims import confirmed_admission
from ynoy.decision_identity import admit_decision_claim, build_claim_identity
from ynoy.models import CandidateKind, DecisionLabel, PersonaStratum, TargetLayer
from ynoy.models.formal_decision import AdmittedDecisionClaim


def admitted_claim(
    *,
    offset: int = 0,
    decision_key: str = "synthetic-change-decision",
    decision_label: DecisionLabel = DecisionLabel.REJECT,
    target_layer: TargetLayer = TargetLayer.SCOPED_POLICY,
    subject_id: str = "self",
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    supersedes_claim_id: UUID | None = None,
) -> AdmittedDecisionClaim:
    persona = target_layer == TargetLayer.PERSONA_CANDIDATE
    _, correction, admission = confirmed_admission(
        offset=offset,
        subject_id=subject_id,
        decision_label=decision_label,
        target_layer=target_layer,
        persona_kind=CandidateKind.PREFERENCE if persona else None,
        persona_stratum=PersonaStratum.DECISIONS_AND_POLICY if persona else None,
        valid_from=valid_from,
        valid_until=valid_until,
        supersedes_claim_id=supersedes_claim_id,
    )
    identity = build_claim_identity(
        admission.claim,
        reviewed_decision_key=decision_key,
        decision_key_receipt_sha256=correction.receipt_sha256,
    )
    return admit_decision_claim(admission.claim, identity)
