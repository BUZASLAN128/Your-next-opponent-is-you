from __future__ import annotations

from ynoy.errors import AdapterError
from ynoy.full_persona.response_context import PersonaContextEntry
from ynoy.full_persona.response_protocol import PersonaResponseCandidate
from ynoy.models.persona_response import PersonaGenerationSource, PersonaResponseArm
from ynoy.persona_similarity import max_source_ngram_overlap

_MAX_SOURCE_OVERLAP = 0.75


def validate_response_originality(
    candidate: PersonaResponseCandidate,
    context: tuple[PersonaContextEntry, ...],
    arm: PersonaResponseArm,
    generation_source: PersonaGenerationSource,
) -> None:
    """Reject source-like model prose while preserving explicit deterministic quotations."""
    if arm != "structured" or generation_source != "local_model" or not context:
        return
    sources = tuple(item.claim for item in context)
    if max_source_ngram_overlap(candidate.response_text, sources) > _MAX_SOURCE_OVERLAP:
        raise AdapterError(
            "persona_responder_source_copy",
            "The local persona response copied too much source wording.",
        )
