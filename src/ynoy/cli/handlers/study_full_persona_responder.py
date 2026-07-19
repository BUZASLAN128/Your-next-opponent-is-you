from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.errors import PolicyViolation
from ynoy.full_persona.pack_store import FullPersonaPackStore
from ynoy.full_persona.responder import LocalPersonaResponder


def respond_full_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    pack = FullPersonaPackStore(
        context.settings.require_private_root(), synthetic=synthetic
    ).read_pack(args.run_id)
    result = _configured_responder(context).respond(pack, args.query, arm=args.arm)
    return {
        "status": "unvalidated_persona_simulation",
        **result.model_dump(mode="json"),
        "private_content_emitted": True,
    }


def _configured_responder(context: CommandContext) -> LocalPersonaResponder:
    settings = context.settings
    if not (
        settings.local_reasoner_url
        and settings.local_reasoner_model_explicit
        and settings.local_reasoner_revision
        and settings.local_reasoner_artifact_sha256
    ):
        raise PolicyViolation(
            "persona_responder_not_configured",
            "Configure the pinned loopback model, revision, and artifact SHA-256.",
        )
    return LocalPersonaResponder(
        endpoint=settings.local_reasoner_url,
        model=settings.local_reasoner_model,
        revision=settings.local_reasoner_revision,
        artifact_sha256=settings.local_reasoner_artifact_sha256,
        local_attested=settings.local_model_attested,
    )
