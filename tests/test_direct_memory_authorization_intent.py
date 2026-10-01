from __future__ import annotations

from pathlib import Path

import pytest

from tests.direct_memory_fixtures import CLAIM_ID, NOW, PROJECT
from tests.test_direct_memory_store import SYNTHETIC_PLANE, _decision_digest, _stored_review
from ynoy.direct_memory import AuthorizationIntent, DirectMemoryStore
from ynoy.errors import DataValidationError
from ynoy.models import ConfirmClaimDecision


@pytest.mark.parametrize(
    "field",
    ("action", "payload_sha256", "subject_id", "review_sha256"),
)
def test_live_user_authorization_intent_binds_every_correction_dimension(
    tmp_path: Path, field: str
) -> None:
    store = DirectMemoryStore(
        tmp_path / "memory.sqlite3", clock=lambda: NOW, data_plane=SYNTHETIC_PLANE
    )
    stored = _stored_review(store)
    decisions = (ConfirmClaimDecision(claim_id=CLAIM_ID, subject_id="self"),)
    digest = _decision_digest(decisions)
    intent_values: dict[str, object] = {
        "action": "correct",
        "payload_sha256": digest,
        "subject_id": "self",
        "review_sha256": stored.review_sha256,
    }
    request = dict(intent_values)
    request[field] = {
        "action": "retract",
        "payload_sha256": "f" * 64,
        "subject_id": "other",
        "review_sha256": "e" * 64,
    }[field]
    intent = AuthorizationIntent(**intent_values)
    store.record_live_user_input(
        source_id="live-bound-differently",
        project=PROJECT,
        said_at=NOW,
        exact_text="A separately bound authorization declaration.",
        authorization_intent=intent,
        expected_revision=store.current_revision(PROJECT),
    )
    with pytest.raises(DataValidationError) as blocked:
        store.authorize_action("live-bound-differently", **request)
    assert blocked.value.code == "direct_memory_authorization_mismatch"
