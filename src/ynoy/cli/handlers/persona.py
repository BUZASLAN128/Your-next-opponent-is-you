from __future__ import annotations

import argparse

from ynoy.cli.context import CommandContext
from ynoy.models import DataClass
from ynoy.persona import build_persona_preview
from ynoy.storage import MemoryRepository
from ynoy.util import utc_now


def handle_persona(args: argparse.Namespace, context: CommandContext) -> dict[str, object]:
    """Build a non-authoritative projection from active canonical claims."""
    synthetic = bool(args.synthetic)
    data_class = DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
    repository = MemoryRepository(
        context.database(synthetic=synthetic), inference_data_class=data_class
    )
    claims = repository.list_active_canonical_claims(
        subject_id=args.subject_id,
        evaluation_time=utc_now(),
    )
    persona_claims = tuple(item for item in claims if item.persona_stratum is not None)
    return build_persona_preview(persona_claims).model_dump(mode="json")
