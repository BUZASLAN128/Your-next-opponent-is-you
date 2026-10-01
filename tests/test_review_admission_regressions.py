"""Synthetic regressions from the independently reproduced baseline review."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from test_interaction_correction import _NOW, _review

from ynoy.correction import build_correction_receipt, interaction_review_sha256
from ynoy.errors import DataValidationError
from ynoy.interaction_review import build_interaction_review
from ynoy.models import ConfirmClaimDecision, SourceSpan
from ynoy.models.interaction import InteractionReview
from ynoy.review_replay import replay_interaction_review


@pytest.mark.parametrize("end,text", [(1, "FORGED"), (9999, "OUTSIDE")])
@pytest.mark.parametrize("gate", ["json", "model", "digest", "correction", "replay"])
def test_review_admission_rejects_forged_exact_evidence(end: int, text: str, gate: str) -> None:
    review = _review()
    span = SourceSpan(character_start=0, character_end=end, text=text)
    claim = review.claims[0].model_copy(update={"source_spans": (span,)})
    bad = review.model_copy(update={"claims": (claim,), "claim_count": 1})
    decision = ConfirmClaimDecision(claim_id=claim.record_id, subject_id="self")
    with pytest.raises((DataValidationError, ValidationError)):
        if gate == "json":
            InteractionReview.model_validate_json(bad.model_dump_json())
        elif gate == "model":
            InteractionReview.model_validate(bad.model_dump(mode="python"))
        elif gate == "digest":
            interaction_review_sha256(bad)
        elif gate == "correction":
            build_correction_receipt(bad, (decision,), created_at=_NOW)
        else:
            replay_interaction_review(bad, ())


@pytest.mark.parametrize("kind", ["naive_exact", "fractional_date_only", "naive_created"])
def test_source_timestamp_precision_is_enforced_on_reload_and_builder(kind: str) -> None:
    review = _review()
    updates: dict[str, object] = {"event_time": _NOW.replace(tzinfo=None)}
    if kind == "fractional_date_only":
        updates = {
            "event_time": _NOW.replace(hour=0, minute=0, second=0, microsecond=1),
            "event_time_precision": "date_only",
        }
    elif kind == "naive_created":
        updates = {"created_at": _NOW.replace(tzinfo=None)}
    bad = review.source.model_copy(update=updates)
    with pytest.raises((DataValidationError, ValidationError)):
        build_interaction_review(bad, review.claims)
    with pytest.raises(ValidationError):
        type(bad).model_validate_json(bad.model_dump_json())


def test_valid_reload_keeps_existing_review_hash_and_exact_source() -> None:
    review = _review()
    loaded = InteractionReview.model_validate_json(review.model_dump_json())
    assert loaded.source.response == review.source.response
    assert loaded.model_dump(mode="json") == review.model_dump(mode="json")
    assert interaction_review_sha256(loaded) == interaction_review_sha256(review)
