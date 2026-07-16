from __future__ import annotations

import json
import re
from typing import Literal, cast

from ynoy.errors import DataValidationError
from ynoy.models import AnnotationPresentation, DataClass, PersonaProposalBundle, StudyArtifactIndex
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.persona_study.assisted_review import review_payloads
from ynoy.persona_study.label_contract import dependencies, derived_class, has_entry
from ynoy.util import canonical_json_bytes

PROPOSALS_PATH = "evaluator/model-proposals.json"
RETRY_PROPOSALS_PATH = "evaluator/model-proposals.retry-01.json"
RETRY_LINK_PATH = "evaluator/model-proposals.retry-01-link.json"
ProposalAttempt = Literal["primary", "retry_01"]


def attempt_context(
    store: PersonaStudyStore,
    index: StudyArtifactIndex,
    study_id: str,
    attempt: ProposalAttempt,
) -> tuple[str, str | None]:
    if attempt == "primary":
        if has_entry(index, PROPOSALS_PATH):
            raise DataValidationError(
                "persona_proposals_already_exist",
                "A model proposal receipt already exists for this immutable study.",
            )
        return PROPOSALS_PATH, None
    if not has_entry(index, PROPOSALS_PATH) or has_entry(index, RETRY_PROPOSALS_PATH):
        raise DataValidationError(
            "persona_proposal_retry_unavailable",
            "The bounded retry requires exactly one failed primary proposal receipt.",
        )
    return RETRY_PROPOSALS_PATH, _failed_primary_receipt(store, study_id)


def build_attempt_payloads(
    index: StudyArtifactIndex,
    bundle: PersonaProposalBundle,
    cards: tuple[AnnotationPresentation, ...],
    proposal_path: str,
    attempt: ProposalAttempt,
    previous_receipt: str | None,
) -> tuple[ArtifactPayload, ...]:
    data_class = derived_class(index)
    content_class = (
        DataClass.PUBLIC_SYNTHETIC
        if data_class == DataClass.PUBLIC_SYNTHETIC
        else DataClass.RAW_CORPUS
    )
    sources = dependencies(index)
    payloads = [
        ArtifactPayload(
            proposal_path,
            canonical_json_bytes(bundle.model_dump(mode="json")),
            content_class,
            sources,
        )
    ]
    if previous_receipt:
        payloads.append(_retry_link(bundle, previous_receipt, data_class, sources))
    if bundle.receipt.status == "review_ready":
        payloads.extend(review_payloads(bundle, cards, content_class, sources, attempt))
    return tuple(payloads)


def _failed_primary_receipt(store: PersonaStudyStore, study_id: str) -> str:
    try:
        value = json.loads(store.read_artifact(study_id, PROPOSALS_PATH))
        receipt = value["receipt"]
        digest = receipt["receipt_sha256"]
        if receipt["status"] != "unreliable" or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError
        return cast(str, digest)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "persona_proposal_retry_unavailable",
            "The primary proposal receipt is not an eligible failed attempt.",
        ) from exc


def _retry_link(
    bundle: PersonaProposalBundle,
    previous_receipt: str,
    data_class: DataClass,
    sources: tuple[str, ...],
) -> ArtifactPayload:
    return ArtifactPayload(
        RETRY_LINK_PATH,
        canonical_json_bytes(
            {
                "schema_version": "persona-proposal-retry-link/0.1",
                "previous_receipt_sha256": previous_receipt,
                "retry_receipt_sha256": bundle.receipt.receipt_sha256,
                "reason": "previous_attempt_unreliable",
            }
        ),
        data_class,
        sources,
    )
