from __future__ import annotations

import json
from pathlib import Path

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers import study_local_authenticator
from ynoy.cli.parser import parse_args
from ynoy.config import Settings


def _context(private_root: Path) -> CommandContext:
    return CommandContext(
        settings=Settings.from_environment(private_root=private_root),
        repository_root=private_root,
    )


def test_local_authenticator_status_is_aggregate_only_for_unenrolled_root(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "private-root"
    private_root.mkdir()
    result = study_local_authenticator.local_authenticator_status(
        parse_args(["study", "local-authenticator-status"]),
        _context(private_root),
    )

    assert result["status"] == "not_ready"
    assert result["enrolled"] is False
    assert result["exact_challenge_binding"] is True
    assert result["automatic_adoption"] is False
    assert result["credential_material_emitted"] is False
    encoded = json.dumps(result)
    assert str(private_root) not in encoded
    assert "fingerprint" not in encoded
    assert "public_key" not in encoded
    assert "private_key" not in encoded


def test_enroll_local_authenticator_uses_injected_boundary_without_interactive_process(
    tmp_path: Path, monkeypatch
) -> None:
    calls: dict[str, object] = {}

    class FakeRunner:
        available = True

    class FakeAuthenticator:
        def __init__(self, *, root: Path, runner: FakeRunner) -> None:
            calls["root"] = root
            calls["runner"] = runner

        def enroll_with_system_openssh(self, *, actor_id: str) -> None:
            calls["actor_id"] = actor_id

    monkeypatch.setattr(study_local_authenticator, "OpenSshSignatureRunner", FakeRunner)
    monkeypatch.setattr(
        study_local_authenticator,
        "LocalSshAdoptionAuthenticator",
        FakeAuthenticator,
    )
    result = study_local_authenticator.enroll_local_authenticator(
        parse_args(["study", "enroll-local-authenticator", "local-user"]),
        _context(tmp_path / "private-root"),
    )

    assert result == {
        "status": "local_authenticator_enrolled",
        "method": "openssh_passphrase_signature",
        "exact_challenge_binding": True,
        "credential_material_emitted": False,
        "automatic_adoption": False,
        "authority": "adoption_receipt_only",
    }
    assert calls["actor_id"] == "local-user"
    assert isinstance(calls["runner"], FakeRunner)
    assert calls["root"] == tmp_path / "private-root"
