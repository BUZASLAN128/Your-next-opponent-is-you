from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from ynoy.errors import AdapterError, DataValidationError, PolicyViolation
from ynoy.full_persona.local_model_artifact import verify_local_model_artifact
from ynoy.full_persona.response_context import (
    PersonaContextEntry,
    PersonaStyleSignal,
)
from ynoy.full_persona.response_guard import public_uncertainties, runtime_guard_candidate
from ynoy.full_persona.response_protocol import PersonaResponseCandidate
from ynoy.full_persona.response_runtime import (
    build_evidence_packet,
    generate_persona_candidate,
    require_verified_artifact,
)
from ynoy.local_http import post_json
from ynoy.models.full_persona_pack import PersonaPack
from ynoy.models.interaction import ReviewProviderEvidence
from ynoy.models.persona_response import (
    PersonaGenerationSource,
    PersonaResponse,
    PersonaResponseArm,
    response_hashes,
)
from ynoy.policy import is_loopback_url
from ynoy.util import sha256_text, utc_now

_MAX_QUERY_CHARS = 4_096


@dataclass(frozen=True, slots=True)
class LocalPersonaResponder:
    endpoint: str
    model: str
    revision: str
    artifact_sha256: str
    local_attested: bool
    artifact_path: Path | None = None
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not is_loopback_url(self.endpoint):
            raise DataValidationError(
                "persona_responder_not_loopback",
                "The persona responder endpoint must use HTTP on a loopback address.",
            )
        if not self.local_attested:
            raise PolicyViolation(
                "persona_responder_attestation_required",
                "Private persona responses require an explicitly attested local endpoint.",
            )
        try:
            provider = self.provider_evidence
        except ValidationError as exc:
            raise DataValidationError(
                "persona_responder_identity_invalid",
                "The persona responder requires canonical pinned model identity.",
            ) from exc
        del provider
        if self.artifact_path is not None:
            verify_local_model_artifact(
                self.artifact_path, self.artifact_sha256, prefix="persona_responder"
            )

    @property
    def provider_evidence(self) -> ReviewProviderEvidence:
        return ReviewProviderEvidence(
            model=self.model,
            revision=self.revision,
            artifact_sha256=self.artifact_sha256,
            local_attested=True,
        )

    def respond(
        self,
        pack: PersonaPack,
        query: str,
        *,
        arm: PersonaResponseArm = "structured",
    ) -> PersonaResponse:
        selected_arm = _validate_arm(arm)
        normalized_query = _validate_query(query)
        validated_pack = _validated_pack(pack)
        require_verified_artifact(validated_pack, self.artifact_path, self.artifact_sha256)
        guarded = runtime_guard_candidate(normalized_query, selected_arm)
        if guarded is not None:
            return _materialize(
                guarded,
                (),
                (),
                validated_pack,
                normalized_query,
                selected_arm,
                self,
                "deterministic_runtime_guard",
            )
        packet = build_evidence_packet(validated_pack, normalized_query, selected_arm)
        candidate, generation_source = generate_persona_candidate(
            endpoint=self.endpoint,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            artifact_path=self.artifact_path,
            artifact_sha256=self.artifact_sha256,
            query=normalized_query,
            arm=selected_arm,
            packet=packet,
            transport=post_json,
        )
        _validate_citations(candidate, packet.context, packet.style, selected_arm)
        return _materialize(
            candidate,
            packet.context,
            packet.style,
            validated_pack,
            normalized_query,
            selected_arm,
            self,
            generation_source,
        )


def _validate_arm(arm: str) -> PersonaResponseArm:
    if arm not in {"structured", "generic"}:
        raise DataValidationError(
            "persona_responder_arm_invalid", "Persona response arm is not supported."
        )
    return cast(PersonaResponseArm, arm)


def _validated_pack(pack: PersonaPack) -> PersonaPack:
    try:
        validated = PersonaPack.model_validate(pack.model_dump(mode="json"))
    except (AttributeError, ValidationError) as exc:
        raise DataValidationError(
            "persona_responder_pack_invalid",
            "The persona responder requires a canonical provenance-bound pack.",
        ) from exc
    if validated.expires_at <= utc_now():
        raise DataValidationError(
            "persona_responder_pack_expired",
            "The persona responder refuses an expired private pack.",
        )
    return validated


def _validate_query(query: str) -> str:
    value = query.strip()
    if not value:
        raise DataValidationError(
            "persona_responder_query_empty", "Persona response requires a non-empty query."
        )
    if len(value) > _MAX_QUERY_CHARS:
        raise DataValidationError(
            "persona_responder_input_too_large",
            "The bounded persona response query exceeded its character limit.",
        )
    return value


def _validate_citations(
    candidate: PersonaResponseCandidate,
    context: tuple[PersonaContextEntry, ...],
    style: tuple[PersonaStyleSignal, ...],
    arm: PersonaResponseArm,
) -> None:
    supplied = {item.atom_id for item in context}
    supplied.update(support.atom_id for signal in style for support in signal.supports)
    cited = set(candidate.used_atom_ids)
    invalid = len(cited) != len(candidate.used_atom_ids) or not cited <= supplied
    if arm == "generic" and cited:
        invalid = True
    if arm == "structured" and supplied and not cited:
        invalid = True
    if invalid:
        raise AdapterError(
            "persona_responder_atom_ids_invalid",
            "The local persona response cited unavailable or duplicate evidence.",
        )


def _materialize(
    candidate: PersonaResponseCandidate,
    context: tuple[PersonaContextEntry, ...],
    style: tuple[PersonaStyleSignal, ...],
    pack: PersonaPack,
    query: str,
    arm: PersonaResponseArm,
    responder: LocalPersonaResponder,
    generation_source: PersonaGenerationSource,
) -> PersonaResponse:
    used_ids = tuple(sorted(candidate.used_atom_ids))
    receipt_map = _receipt_map(context, style)
    receipts = tuple(sorted({value for atom_id in used_ids for value in receipt_map[atom_id]}))
    payload = _response_payload(
        candidate,
        pack,
        query,
        arm,
        responder,
        generation_source,
        used_ids,
        receipts,
    )
    provenance, response = response_hashes(payload)
    return PersonaResponse.model_validate(
        {**payload, "provenance_sha256": provenance, "response_sha256": response}
    )


def _receipt_map(
    context: tuple[PersonaContextEntry, ...], style: tuple[PersonaStyleSignal, ...]
) -> dict[str, tuple[str, ...]]:
    result = {item.atom_id: item.evidence_receipts for item in context}
    for signal in style:
        for support in signal.supports:
            result[support.atom_id] = support.evidence_receipts
    return result


def _response_payload(
    candidate: PersonaResponseCandidate,
    pack: PersonaPack,
    query: str,
    arm: PersonaResponseArm,
    responder: LocalPersonaResponder,
    generation_source: PersonaGenerationSource,
    used_ids: tuple[str, ...],
    receipts: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "protocol_version": "persona-response/0.1",
        "arm": arm,
        "query_sha256": sha256_text(query),
        "response_text": candidate.response_text.strip(),
        "used_atom_ids": used_ids,
        "evidence_receipts": receipts,
        "uncertainties": public_uncertainties(arm),
        "should_abstain": candidate.should_abstain,
        "generation_source": generation_source,
        **_source_binding(pack),
        **_model_binding(responder),
        **_safety_state(arm),
    }


def _source_binding(pack: PersonaPack) -> dict[str, Any]:
    return {
        "pack_id": pack.pack_id,
        "pack_sha256": pack.pack_sha256,
        "source_manifest_sha256": pack.source_manifest_sha256,
        "source_head_sha256": pack.source_head_sha256,
        "source_head_revision": pack.source_head_revision,
        "data_class": pack.data_class,
        "synthetic": pack.synthetic,
        "expires_at": pack.expires_at,
    }


def _model_binding(responder: LocalPersonaResponder) -> dict[str, Any]:
    return {
        "model": responder.model,
        "revision": responder.revision,
        "artifact_sha256": responder.artifact_sha256,
        "model_identity_status": "locally_attested_not_endpoint_authenticated",
    }


def _safety_state(arm: PersonaResponseArm) -> dict[str, Any]:
    return {
        "judgment_basis": "abstention",
        "simulation_mode": (
            "structured_persona_candidate" if arm == "structured" else "generic_control"
        ),
        "calibration_status": "not_calibrated",
        "authority": "none",
        "action_status": "not_performed",
        "send_enabled": False,
        "execute_enabled": False,
        "automatic_core": False,
        "persistent": False,
        "retention_bound_to_pack": True,
        "protected_holdout_used": False,
        "target_object_accepted": False,
        "target_seen": False,
        "persona_quality_claimed": False,
    }
