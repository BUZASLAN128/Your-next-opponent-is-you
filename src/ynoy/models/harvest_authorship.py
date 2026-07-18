from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from pydantic import Field, model_validator

from ynoy.models.base import StrictModel
from ynoy.util import canonical_sha256

HarvestAuthorshipValue = Literal["self", "other", "mixed", "unknown"]
HarvestCandidateId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]


class HarvestAuthorshipSubmission(StrictModel):
    source_study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_ids: tuple[HarvestCandidateId, ...] = Field(min_length=1, max_length=13)
    authorships: tuple[HarvestAuthorshipValue, ...] = Field(min_length=1, max_length=13)
    actor: Literal["represented_user"] = "represented_user"
    judgment_signal: None = None
    adoption: None = None
    core_eligible: Literal[False] = False
    benchmark_eligible: Literal[False] = False
    decision_atoms_projected: Literal[False] = False


class HarvestAuthorshipReceipt(StrictModel):
    protocol_version: Literal["codex-harvest-authorship/0.1"] = "codex-harvest-authorship/0.1"
    source_study_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_freeze_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selector_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_dependencies_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_ids: tuple[HarvestCandidateId, ...] = Field(min_length=1, max_length=12)
    candidate_sha256s: tuple[str, ...] = Field(min_length=1, max_length=12)
    authorships: tuple[Literal["self"], ...] = Field(min_length=1, max_length=12)
    candidate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    submission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: Literal["represented_user"] = "represented_user"
    authenticator_verified: Literal[False] = False
    claim_holder: None = None
    judgment_signal: None = None
    adoption: None = None
    core_eligible: Literal[False] = False
    benchmark_eligible: Literal[False] = False
    decision_atoms_projected: Literal[False] = False
    database_used: Literal[False] = False
    model_provider_used: Literal[False] = False
    automatic_core_promotion: Literal[False] = False
    persona_quality_claimed: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_contract_matches(self) -> HarvestAuthorshipReceipt:
        size = len(self.candidate_ids)
        if size != len(self.authorships) or size != len(self.candidate_sha256s):
            raise ValueError("harvest authorship receipt candidate tuples disagree")
        expected_set = canonical_sha256(
            {
                "candidate_ids": self.candidate_ids,
                "candidate_sha256s": self.candidate_sha256s,
                "authorships": self.authorships,
            }
        )
        if self.candidate_set_sha256 != expected_set:
            raise ValueError("harvest authorship candidate-set receipt does not match")
        expected = canonical_sha256(self.model_dump(mode="json", exclude={"receipt_sha256"}))
        if self.receipt_sha256 != expected:
            raise ValueError("harvest authorship receipt hash does not match")
        return self


def seal_harvest_authorship_receipt(**values: object) -> HarvestAuthorshipReceipt:
    draft = cast(Any, HarvestAuthorshipReceipt).model_construct(**values, receipt_sha256="0" * 64)
    payload = draft.model_dump(mode="json", exclude={"receipt_sha256"})
    return HarvestAuthorshipReceipt.model_validate(
        {**payload, "receipt_sha256": canonical_sha256(payload)}
    )
