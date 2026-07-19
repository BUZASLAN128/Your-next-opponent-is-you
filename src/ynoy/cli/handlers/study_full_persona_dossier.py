from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.full_persona.dossier import build_persona_dossier
from ynoy.full_persona.pack_store import FullPersonaPackStore


def profile_full_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    synthetic = bool(args.synthetic)
    store = FullPersonaPackStore(context.settings.require_private_root(), synthetic=synthetic)
    dossier = build_persona_dossier(store.read_pack(args.run_id))
    return {
        "status": "private_unadopted_persona_dossier",
        **dossier.model_dump(mode="json"),
        "storage": "ephemeral_stdout_only",
        "judgment_basis": "abstention",
        "action_status": "not_performed",
        "send_enabled": False,
        "execute_enabled": False,
    }
