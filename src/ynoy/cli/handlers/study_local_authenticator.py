from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.local_adoption import LocalSshAdoptionAuthenticator, OpenSshSignatureRunner


def enroll_local_authenticator(
    args: argparse.Namespace, context: CommandContext
) -> dict[str, object]:
    """Run the system OpenSSH enrollment UI without emitting credential material."""
    runner = OpenSshSignatureRunner()
    authenticator = LocalSshAdoptionAuthenticator(
        root=context.settings.require_private_root(), runner=runner
    )
    authenticator.enroll_with_system_openssh(actor_id=str(args.actor_id))
    return {
        "status": "local_authenticator_enrolled",
        "method": "openssh_passphrase_signature",
        "exact_challenge_binding": True,
        "credential_material_emitted": False,
        "automatic_adoption": False,
        "authority": "adoption_receipt_only",
    }


def local_authenticator_status(
    args: argparse.Namespace, context: CommandContext
) -> dict[str, object]:
    del args
    runner = OpenSshSignatureRunner()
    authenticator = LocalSshAdoptionAuthenticator(
        root=context.settings.require_private_root(), runner=runner
    )
    return {
        "status": "ready" if runner.available and authenticator.enrolled else "not_ready",
        "openssh_available": runner.available,
        "enrolled": authenticator.enrolled,
        "exact_challenge_binding": True,
        "automatic_adoption": False,
        "credential_material_emitted": False,
    }
