from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ynoy.errors import DataValidationError
from ynoy.full_persona.local_model_artifact import verify_local_model_artifact
from ynoy.full_persona.persona_package import (
    build_full_persona_package,
    persona_prompt_profile,
)
from ynoy.full_persona.response_context import (
    PersonaContextEntry,
    PersonaStyleSignal,
    select_response_context,
    select_style_signals,
)
from ynoy.full_persona.response_guard import biography_evidence_candidate
from ynoy.full_persona.response_protocol import (
    PersonaResponseCandidate,
    build_response_request,
    citation_aliases,
    parse_response_candidate,
    resolve_candidate_citations,
)
from ynoy.local_http import post_json
from ynoy.models.full_persona_pack import PersonaPack
from ynoy.models.persona_response import (
    PersonaGenerationSource,
    PersonaResponseArm,
)

_MAX_RESPONSE_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class PersonaEvidencePacket:
    context: tuple[PersonaContextEntry, ...]
    style: tuple[PersonaStyleSignal, ...]
    profile: dict[str, object] | None


class PersonaTransport(Protocol):
    def __call__(
        self,
        endpoint: str,
        payload: object,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
        error_prefix: str,
    ) -> object: ...


def build_evidence_packet(
    pack: PersonaPack, query: str, arm: PersonaResponseArm
) -> PersonaEvidencePacket:
    if arm == "generic":
        return PersonaEvidencePacket((), (), None)
    return PersonaEvidencePacket(
        context=select_response_context(pack, query),
        style=select_style_signals(pack),
        profile=persona_prompt_profile(build_full_persona_package(pack)),
    )


def require_verified_artifact(
    pack: PersonaPack, artifact_path: Path | None, artifact_sha256: str
) -> None:
    if not pack.synthetic and artifact_path is None:
        raise DataValidationError(
            "persona_responder_artifact_required",
            "A private persona response requires the pinned local artifact file.",
        )
    if artifact_path is not None:
        verify_local_model_artifact(artifact_path, artifact_sha256, prefix="persona_responder")


def request_persona_candidate(
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
    artifact_path: Path | None,
    artifact_sha256: str,
    query: str,
    arm: PersonaResponseArm,
    packet: PersonaEvidencePacket,
    transport: PersonaTransport = post_json,
) -> PersonaResponseCandidate:
    raw = transport(
        endpoint,
        build_response_request(model, query, packet.context, arm, packet.style, packet.profile),
        timeout_seconds=timeout_seconds,
        max_response_bytes=_MAX_RESPONSE_BYTES,
        error_prefix="persona_responder",
    )
    candidate = resolve_candidate_citations(
        parse_response_candidate(raw, model), citation_aliases(packet.context, packet.style)
    )
    if artifact_path is not None:
        verify_local_model_artifact(artifact_path, artifact_sha256, prefix="persona_responder")
    return candidate


def generate_persona_candidate(
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
    artifact_path: Path | None,
    artifact_sha256: str,
    query: str,
    arm: PersonaResponseArm,
    packet: PersonaEvidencePacket,
    transport: PersonaTransport = post_json,
) -> tuple[PersonaResponseCandidate, PersonaGenerationSource]:
    biography = biography_evidence_candidate(query, arm, packet.context)
    if biography is not None:
        return biography, "deterministic_evidence_projection"
    candidate = request_persona_candidate(
        endpoint=endpoint,
        model=model,
        timeout_seconds=timeout_seconds,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        query=query,
        arm=arm,
        packet=packet,
        transport=transport,
    )
    return candidate, "local_model"
