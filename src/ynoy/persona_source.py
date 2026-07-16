from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from pydantic import ValidationError

from ynoy.constants import (
    DEFAULT_BOOTSTRAP_MAX_DECLARATIONS,
    DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES,
    DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES,
)
from ynoy.errors import DataValidationError
from ynoy.models import (
    AdoptedPersonaDeclaration,
    CandidateKind,
    DataClass,
    DecisionLabel,
    ScopeRef,
)
from ynoy.util import sha256_bytes

PERSONA_SOURCE_NAMESPACE = UUID("f3414426-7539-4cc5-a050-b59292f7801f")


def load_adopted_persona_source(
    path: Path, *, synthetic: bool = False
) -> list[AdoptedPersonaDeclaration]:
    source = path.expanduser().resolve(strict=True)
    if not source.is_file():
        raise DataValidationError("persona_source_not_file", "Persona source is not a file.")
    if source.suffix.casefold() != ".json":
        raise DataValidationError(
            "persona_json_required",
            "Persona declarations require structured JSON with explicit adoption metadata.",
        )
    raw_bytes, text = _read_bounded_source(source)
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataValidationError("persona_json_invalid", "Persona JSON is invalid.") from exc
    if not isinstance(raw, list):
        raise DataValidationError("persona_array_required", "Persona JSON must be an array.")
    _validate_count(len(raw))
    source_digest = sha256_bytes(raw_bytes)
    declarations = [
        _parse_declaration(
            value,
            index=index,
            source_name=source.name,
            source_digest=source_digest,
            synthetic=synthetic,
        )
        for index, value in enumerate(raw)
    ]
    if not declarations:
        raise DataValidationError(
            "persona_source_empty", "Persona source contains no declarations."
        )
    return declarations


def _parse_declaration(
    value: object,
    *,
    index: int,
    source_name: str,
    source_digest: str,
    synthetic: bool,
) -> AdoptedPersonaDeclaration:
    if not isinstance(value, dict):
        raise DataValidationError(
            "persona_object_required", "Every persona declaration must be an object."
        )
    _require_explicit_adoption(value, synthetic=synthetic)
    statement = _validated_statement(value.get("statement"))
    subject_id = _subject_id(value)
    try:
        return AdoptedPersonaDeclaration(
            record_id=_stable_id(source_digest, index, statement),
            source_record_id=_stable_source_id(source_digest),
            source_name=source_name,
            subject_id=subject_id,
            kind=CandidateKind(str(value.get("kind", CandidateKind.PREFERENCE.value))),
            statement=statement,
            scope=_scope(value.get("scope"), subject_id=subject_id),
            decision_label=_decision_label(value.get("decision_label")),
            data_class=(DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY),
            synthetic=synthetic,
        )
    except (ValueError, ValidationError) as exc:
        raise DataValidationError(
            "persona_declaration_invalid",
            f"Persona declaration at index {index} is invalid.",
        ) from exc


def _require_explicit_adoption(value: dict[object, object], *, synthetic: bool) -> None:
    required = {
        "speaker": "user",
        "claim_holder": "represented_user",
        "source_authority": "explicit_user_statement",
        "adopted": True,
        "evidence_plane": "identity_interpretation",
        "synthetic": synthetic,
    }
    if any(
        type(value.get(key)) is not type(expected) or value.get(key) != expected
        for key, expected in required.items()
    ):
        raise DataValidationError(
            "persona_explicit_adoption_required",
            "Every persona item requires explicit user authorship, adoption, and plane markers.",
        )


def _scope(value: object, *, subject_id: str) -> ScopeRef:
    if value is None:
        payload: dict[object, object] = {}
    elif isinstance(value, dict):
        payload = dict(value)
    else:
        raise ValueError("scope must be an object")
    payload.setdefault("person_id", subject_id)
    return ScopeRef.model_validate(payload)


def _subject_id(value: dict[object, object]) -> str:
    if "subject_id" in value:
        return _validated_subject(value["subject_id"])
    scope = value.get("scope")
    if isinstance(scope, dict) and "person_id" in scope:
        return _validated_subject(scope["person_id"])
    return "self"


def _validated_subject(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(
            "persona_subject_invalid", "Persona subject identifiers must be non-empty strings."
        )
    if value != value.strip():
        raise DataValidationError(
            "persona_subject_invalid", "Persona subject identifiers must not contain padding."
        )
    return value


def _decision_label(value: object) -> DecisionLabel | None:
    return DecisionLabel(str(value)) if value is not None else None


def _stable_id(source_digest: str, index: int, statement: str) -> UUID:
    return uuid5(PERSONA_SOURCE_NAMESPACE, f"{source_digest}:{index}:{statement}")


def _stable_source_id(source_digest: str) -> UUID:
    return uuid5(PERSONA_SOURCE_NAMESPACE, f"source:{source_digest}")


def _read_bounded_source(source: Path) -> tuple[bytes, str]:
    try:
        if source.stat().st_size > DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES:
            raise DataValidationError(
                "persona_source_too_large",
                "Persona source exceeds the configured byte limit.",
                details={"limit": DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES},
            )
        with source.open("rb") as handle:
            raw = handle.read(DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise DataValidationError(
            "persona_source_unreadable", "Persona source must be readable UTF-8 text."
        ) from exc
    if len(raw) > DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES:
        raise DataValidationError(
            "persona_source_too_large",
            "Persona source grew beyond the configured byte limit.",
            details={"limit": DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES},
        )
    try:
        return raw, raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DataValidationError(
            "persona_source_unreadable", "Persona source must be readable UTF-8 text."
        ) from exc


def _validated_statement(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(
            "persona_statement_required", "Every persona declaration needs a statement."
        )
    if len(value.encode("utf-8")) > DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES:
        raise DataValidationError(
            "persona_statement_too_large",
            "A persona declaration exceeds the configured byte limit.",
            details={"limit": DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES},
        )
    return value


def _validate_count(count: int) -> None:
    if count > DEFAULT_BOOTSTRAP_MAX_DECLARATIONS:
        raise DataValidationError(
            "persona_declaration_limit",
            "Persona source exceeds the configured declaration limit.",
            details={"limit": DEFAULT_BOOTSTRAP_MAX_DECLARATIONS},
        )
