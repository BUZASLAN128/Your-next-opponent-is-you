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
    BootstrapDeclaration,
    CandidateKind,
    DataClass,
    DecisionLabel,
    ScopeRef,
)
from ynoy.util import sha256_bytes

BOOTSTRAP_NAMESPACE = UUID("eb46608d-3bd6-4a37-abda-89fd0a1e9537")


def _stable_record_id(source_digest: str, index: int, statement: str) -> UUID:
    return uuid5(BOOTSTRAP_NAMESPACE, f"{source_digest}:{index}:{statement.strip()}")


def _stable_source_id(source_digest: str) -> UUID:
    return uuid5(BOOTSTRAP_NAMESPACE, f"source:{source_digest}")


def _parse_json_declarations(
    raw: object, *, source_name: str, source_digest: str, synthetic: bool
) -> list[BootstrapDeclaration]:
    if not isinstance(raw, list):
        raise DataValidationError(
            "bootstrap_array_required", "Bootstrap JSON must be an array of declarations."
        )
    _validate_declaration_count(len(raw))
    declarations: list[BootstrapDeclaration] = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            raise DataValidationError(
                "bootstrap_object_required", "Every bootstrap declaration must be an object."
            )
        if synthetic and value.get("synthetic") is not True:
            raise DataValidationError(
                "synthetic_fixture_marker_required",
                "Every D0 bootstrap fixture must declare synthetic=true.",
            )
        statement = _validated_statement(value.get("statement"))
        try:
            kind = CandidateKind(str(value.get("kind", CandidateKind.PREFERENCE.value)))
            subject_id = _subject_id(value)
            scope = _scope_for_subject(value.get("scope", {}), subject_id)
            raw_label = value.get("decision_label")
            decision_label = DecisionLabel(str(raw_label)) if raw_label is not None else None
            declaration = BootstrapDeclaration(
                record_id=_stable_record_id(source_digest, index, statement),
                source_record_id=_stable_source_id(source_digest),
                subject_id=subject_id,
                kind=kind,
                statement=statement.strip(),
                scope=scope,
                decision_label=decision_label,
                source_name=source_name,
                data_class=(
                    DataClass.PUBLIC_SYNTHETIC if synthetic else DataClass.DERIVED_IDENTITY
                ),
                synthetic=synthetic,
            )
        except (ValueError, ValidationError) as exc:
            raise DataValidationError(
                "bootstrap_declaration_invalid",
                f"Bootstrap declaration at index {index} is invalid.",
            ) from exc
        declarations.append(declaration)
    return declarations


def _scope_for_subject(value: object, subject_id: str) -> ScopeRef:
    if not isinstance(value, dict):
        raise ValueError("scope must be an object")
    payload = dict(value)
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
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DataValidationError(
            "bootstrap_subject_invalid",
            "Bootstrap subject identifiers must be non-empty trimmed strings.",
        )
    return value


def load_bootstrap(path: Path, *, synthetic: bool = False) -> list[BootstrapDeclaration]:
    source = path.expanduser().resolve(strict=True)
    if not source.is_file():
        raise DataValidationError("bootstrap_not_file", "Bootstrap source is not a file.")
    if not synthetic:
        raise DataValidationError(
            "real_identity_persistence_unsupported",
            "Real declarations are preview-only until adoption provenance can be persisted.",
        )
    raw_bytes, text = _read_bounded_source(source)
    source_digest = sha256_bytes(raw_bytes)
    if source.suffix.casefold() == ".json":
        try:
            raw: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DataValidationError(
                "bootstrap_json_invalid", "Bootstrap JSON is invalid."
            ) from exc
        declarations = _parse_json_declarations(
            raw,
            source_name=source.name,
            source_digest=source_digest,
            synthetic=synthetic,
        )
    else:
        raise DataValidationError(
            "synthetic_markdown_unsupported",
            "Synthetic bootstrap fixtures must use JSON with explicit synthetic markers.",
        )
    if not declarations:
        raise DataValidationError("bootstrap_empty", "Bootstrap source contains no declarations.")
    return declarations


def _read_bounded_source(source: Path) -> tuple[bytes, str]:
    try:
        if source.stat().st_size > DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES:
            raise DataValidationError(
                "bootstrap_source_too_large",
                "Bootstrap source exceeds the configured byte limit.",
                details={"limit": DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES},
            )
        with source.open("rb") as handle:
            raw = handle.read(DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise DataValidationError(
            "bootstrap_unreadable", "Bootstrap source must be readable UTF-8 text."
        ) from exc
    if len(raw) > DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES:
        raise DataValidationError(
            "bootstrap_source_too_large",
            "Bootstrap source grew beyond the configured byte limit.",
            details={"limit": DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES},
        )
    try:
        return raw, raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DataValidationError(
            "bootstrap_unreadable", "Bootstrap source must be readable UTF-8 text."
        ) from exc


def _validated_statement(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataValidationError(
            "bootstrap_statement_required", "Every declaration needs a non-empty statement."
        )
    normalized = value.strip()
    if len(normalized.encode("utf-8")) > DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES:
        raise DataValidationError(
            "bootstrap_statement_too_large",
            "A bootstrap declaration exceeds the configured byte limit.",
            details={"limit": DEFAULT_BOOTSTRAP_MAX_STATEMENT_BYTES},
        )
    return normalized


def _validate_declaration_count(count: int) -> None:
    if count > DEFAULT_BOOTSTRAP_MAX_DECLARATIONS:
        raise DataValidationError(
            "bootstrap_declaration_limit",
            "Bootstrap source exceeds the configured declaration limit.",
            details={"limit": DEFAULT_BOOTSTRAP_MAX_DECLARATIONS},
        )
