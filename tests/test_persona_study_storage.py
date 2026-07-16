from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ynoy.cli.main import main
from ynoy.errors import DataValidationError
from ynoy.models import DataClass, DeletionProofReceipt
from ynoy.persona_study.artifacts import ArtifactPayload, PersonaStudyStore
from ynoy.util import canonical_json_bytes, canonical_sha256, sha256_bytes


def _payload(name: str, dependency: str) -> ArtifactPayload:
    return ArtifactPayload(
        f"evaluator/{name}.json", b"{}", DataClass.PUBLIC_SYNTHETIC, (dependency,)
    )


def _expired_run(store: PersonaStudyStore, run_id: str, now: datetime) -> None:
    store.write_run(
        run_id,
        (_payload("expired", canonical_sha256(run_id)),),
        created_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),
    )


def _write_tombstone(
    store: PersonaStudyStore, proof_id: str, created_at: datetime
) -> tuple[DeletionProofReceipt, Path]:
    receipt = DeletionProofReceipt(
        proof_id=proof_id,
        source_dependency=canonical_sha256((proof_id, "source")),
        first_bundle_sha256=canonical_sha256((proof_id, "first")),
        regenerated_bundle_sha256=canonical_sha256((proof_id, "first")),
        first_deleted_count=1,
        second_deleted_count=1,
        created_at=created_at,
        expires_at=created_at + timedelta(days=7),
    )
    path = store.paths.tombstone(proof_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(receipt.model_dump(mode="json")))
    return receipt, path


def test_status_access_purges_an_expired_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_root = tmp_path / "private"
    now = datetime.now(UTC)
    store = PersonaStudyStore(
        private_root, real_data=False, evaluation_time=now - timedelta(days=8)
    )
    expired_id = canonical_sha256({"expired-status": True})
    _expired_run(store, expired_id, now)

    exit_code = main(
        [
            "--indent",
            "0",
            "--private-root",
            str(private_root),
            "study",
            "status",
            expired_id,
            "--synthetic",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["error"]["code"] == "persona_study_not_found"
    assert not (store.runs / expired_id).exists()


def test_expiry_purge_continues_after_invalid_index(tmp_path: Path) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    private = tmp_path / "private"
    setup = PersonaStudyStore(private, real_data=False, evaluation_time=now - timedelta(days=8))
    valid_ids = (canonical_sha256("valid-a"), canonical_sha256("valid-z"))
    for run_id in valid_ids:
        _expired_run(setup, run_id, now)
    invalid_id = canonical_sha256("invalid-middle")
    _expired_run(setup, invalid_id, now)
    setup.paths.index(invalid_id).write_bytes(b"not-json")
    store = PersonaStudyStore(private, real_data=False, evaluation_time=now)

    result = store.purge_expired(now)

    assert result.deleted_artifact_count == 2
    assert result.failed_run_count == 1
    assert all(not store.paths.control_run(run_id).exists() for run_id in valid_ids)
    assert store.paths.control_run(invalid_id).exists()


def test_store_rejects_junction_like_control_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "private"
    root.mkdir()
    original = Path.is_junction
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path.name == "persona-studies" or original(path),
    )

    with pytest.raises(DataValidationError) as error:
        PersonaStudyStore(root, real_data=False)

    assert error.value.code == "persona_study_link_rejected"


def _mark_link_like(monkeypatch: pytest.MonkeyPatch, target: Path, link_kind: str) -> None:
    method_name = "is_symlink" if link_kind == "symlink" else "is_junction"
    original = getattr(Path, method_name)
    monkeypatch.setattr(
        Path,
        method_name,
        lambda path: path == target or original(path),
    )


@pytest.mark.parametrize("link_kind", ["symlink", "junction"])
@pytest.mark.parametrize(
    "location",
    ["artifact_component", "artifact_file", "tombstone_component", "tombstone_file"],
)
def test_store_rejects_link_redirection_at_private_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
    location: str,
) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    run_id = canonical_sha256("redirected-run")
    proof_id = canonical_sha256("redirected-proof")
    store.write_run(
        run_id,
        (_payload("derived", canonical_sha256("redirected-source")),),
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    targets = {
        "artifact_component": store.paths.evaluator_root / run_id,
        "artifact_file": store.paths.evaluator_root / run_id / "derived.json",
        "tombstone_component": store.paths.tombstones,
        "tombstone_file": store.paths.tombstones / f"{proof_id}.json",
    }
    _mark_link_like(monkeypatch, targets[location], link_kind)

    with pytest.raises(DataValidationError) as error:
        if location.startswith("artifact"):
            store.paths.artifact(run_id, "evaluator/derived.json")
        else:
            store.paths.tombstone(proof_id)

    assert error.value.code == "persona_study_link_rejected"


def test_tombstones_expire_after_seven_days(tmp_path: Path) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    expired_receipt, expired = _write_tombstone(
        store, canonical_sha256("expired-tombstone"), now - timedelta(days=8)
    )
    fresh_receipt, fresh = _write_tombstone(store, canonical_sha256("fresh-tombstone"), now)

    purged = store.purge_expired(now)

    assert expired_receipt.expires_at - expired_receipt.created_at == timedelta(days=7)
    assert fresh_receipt.expires_at - fresh_receipt.created_at == timedelta(days=7)
    assert purged.deleted_tombstone_count == 1 and purged.failed_tombstone_count == 0
    assert not expired.exists() and fresh.is_file()


def test_index_access_purges_expired_tombstone(tmp_path: Path) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    run_id = canonical_sha256("active-run")
    store.write_run(
        run_id,
        (_payload("active", canonical_sha256("active-source")),),
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    _, expired = _write_tombstone(
        store, canonical_sha256("access-expired-tombstone"), now - timedelta(days=8)
    )

    assert store.read_index(run_id).study_id == run_id
    assert not expired.exists()


def test_index_access_fails_on_unindexed_scoped_run(tmp_path: Path) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    active_id = canonical_sha256("active-with-orphan")
    store.write_run(
        active_id,
        (_payload("active", canonical_sha256("active-with-orphan-source")),),
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    orphan_id = canonical_sha256("unindexed-evaluator-run")
    orphan = store.paths.evaluator_root / orphan_id / "orphan.json"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"{}")

    with pytest.raises(DataValidationError) as error:
        store.read_index(active_id)

    assert error.value.code == "persona_study_expiry_purge_incomplete"


@pytest.mark.parametrize("scope", ["annotator_root", "evaluator_root"])
def test_require_absent_detects_unindexed_scoped_artifact(tmp_path: Path, scope: str) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    run_id = canonical_sha256(("orphan", scope))
    orphan = getattr(store.paths, scope) / run_id / "orphan.json"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"{}")
    assert not store.paths.control_run(run_id).exists()

    with pytest.raises(DataValidationError) as error:
        store.require_absent(run_id)

    assert error.value.code == "persona_study_delete_incomplete"


def test_only_declared_user_draft_can_change_before_sealing(tmp_path: Path) -> None:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    store = PersonaStudyStore(tmp_path / "private", real_data=False, evaluation_time=now)
    run_id = canonical_sha256("mutable-draft")
    dependency = canonical_sha256("source")
    store.write_run(
        run_id,
        (
            ArtifactPayload(
                "annotator/labels.template.json",
                b"{}",
                DataClass.PUBLIC_SYNTHETIC,
                (dependency,),
                "represented_user",
            ),
            _payload("manifest", dependency),
        ),
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    draft = store.paths.artifact(run_id, "annotator/labels.template.json")
    draft.write_bytes(b'{"completed_by":"represented_user"}')

    sealed = store.seal_mutable_artifact(
        run_id,
        "annotator/labels.template.json",
        (),
        expected_mutable_sha256=sha256_bytes(draft.read_bytes()),
    )

    assert (
        next(
            item
            for item in sealed.entries
            if item.relative_path == "annotator/labels.template.json"
        ).mutable_by
        == "none"
    )
    draft.write_bytes(b"tampered")
    with pytest.raises(DataValidationError) as error:
        store.delete_run(run_id)
    assert error.value.code == "persona_study_expiry_purge_incomplete"
