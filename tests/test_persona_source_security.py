from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from ynoy.errors import DataValidationError
from ynoy.persona_source import load_adopted_persona_source


def _persona_item(*, synthetic: bool) -> dict[str, object]:
    return {
        "kind": "trait",
        "statement": "Prefer evidence-backed changes.",
        "speaker": "user",
        "claim_holder": "represented_user",
        "source_authority": "explicit_user_statement",
        "adopted": True,
        "evidence_plane": "identity_interpretation",
        "synthetic": synthetic,
    }


def _write_source(path: Path, item: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item]), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("field", "value", "missing"),
    [
        ("speaker", None, True),
        ("claim_holder", None, True),
        ("source_authority", None, True),
        ("adopted", None, True),
        ("evidence_plane", None, True),
        ("synthetic", None, True),
        ("speaker", "assistant", False),
        ("claim_holder", "third_party", False),
        ("source_authority", "system_control", False),
        ("adopted", False, False),
        ("evidence_plane", "control_plane", False),
        ("synthetic", False, False),
    ],
)
def test_persona_source_requires_exact_explicit_adoption_markers(
    field: str,
    value: object,
    missing: bool,
    tmp_path: Path,
) -> None:
    item = _persona_item(synthetic=True)
    if missing:
        item.pop(field)
    else:
        item[field] = value
    source = _write_source(tmp_path / f"invalid-{field}.json", item)

    with pytest.raises(DataValidationError) as blocked:
        load_adopted_persona_source(source, synthetic=True)
    assert blocked.value.code == "persona_explicit_adoption_required"


@pytest.mark.parametrize(
    ("synthetic", "field", "value"),
    [
        pytest.param(True, "adopted", 1, id="adopted-int-one"),
        pytest.param(True, "synthetic", 1, id="synthetic-int-one"),
        pytest.param(False, "synthetic", 0, id="synthetic-int-zero"),
    ],
)
def test_persona_source_rejects_integer_boolean_markers(
    synthetic: bool,
    field: str,
    value: int,
    tmp_path: Path,
) -> None:
    item = _persona_item(synthetic=synthetic)
    item[field] = value
    source = _write_source(tmp_path / f"integer-{field}.json", item)

    with pytest.raises(DataValidationError) as blocked:
        load_adopted_persona_source(source, synthetic=synthetic)
    assert blocked.value.code == "persona_explicit_adoption_required"


def test_persona_source_requires_json(tmp_path: Path) -> None:
    source = tmp_path / "persona.md"
    source.write_text("- I explicitly adopt this statement.", encoding="utf-8")
    with pytest.raises(DataValidationError) as blocked:
        load_adopted_persona_source(source)
    assert blocked.value.code == "persona_json_required"


def test_subject_defaults_to_scope_person_at_parser_boundary(tmp_path: Path) -> None:
    item = _persona_item(synthetic=True)
    item["scope"] = {"person_id": "alice", "project": "pilot"}
    source = _write_source(tmp_path / "scope-default.json", item)

    declaration = load_adopted_persona_source(source, synthetic=True)[0]

    assert declaration.subject_id == "alice"
    assert declaration.scope.person_id == "alice"


def test_loader_preserves_exact_statement_whitespace(tmp_path: Path) -> None:
    statement = " \tExact declaration with whitespace. \r\n"
    item = _persona_item(synthetic=True)
    item["statement"] = statement
    source = _write_source(tmp_path / "exact-statement.json", item)

    declaration = load_adopted_persona_source(source, synthetic=True)[0]

    assert declaration.statement.encode("utf-8") == statement.encode("utf-8")


def test_explicit_subject_scope_mismatch_fails_closed(tmp_path: Path) -> None:
    item = _persona_item(synthetic=True)
    item["subject_id"] = "alice"
    item["scope"] = {"person_id": "bob"}
    source = _write_source(tmp_path / "scope-mismatch.json", item)

    with pytest.raises(DataValidationError) as blocked:
        load_adopted_persona_source(source, synthetic=True)
    assert blocked.value.code == "persona_declaration_invalid"


@pytest.mark.parametrize("location", ["subject", "scope"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param(True, id="bool"),
        pytest.param([], id="list"),
        pytest.param({}, id="object"),
        pytest.param(7, id="numeric"),
        pytest.param("", id="blank"),
        pytest.param(" alice ", id="padded"),
    ],
)
def test_persona_source_rejects_invalid_subject_identifiers(
    location: str,
    value: object,
    tmp_path: Path,
) -> None:
    item = _persona_item(synthetic=True)
    if location == "subject":
        item["subject_id"] = value
    else:
        item["scope"] = {"person_id": value}
    source = _write_source(tmp_path / f"invalid-{location}.json", item)

    with pytest.raises(DataValidationError) as blocked:
        load_adopted_persona_source(source, synthetic=True)
    assert blocked.value.code == "persona_subject_invalid"


def test_persona_growth_guard_reads_at_most_limit_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "growing-persona.json"
    source.write_text("[]", encoding="utf-8")
    read_sizes: list[int] = []

    class ReadSpy(BytesIO):
        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            return super().read(size)

    reader = ReadSpy(b"x" * 32)

    def fake_open(path: Path, mode: str) -> ReadSpy:
        assert path.resolve() == source.resolve() and mode == "rb"
        return reader

    monkeypatch.setattr("ynoy.persona_source.DEFAULT_BOOTSTRAP_MAX_SOURCE_BYTES", 8)
    monkeypatch.setattr(Path, "open", fake_open)
    with pytest.raises(DataValidationError) as blocked:
        load_adopted_persona_source(source, synthetic=True)
    assert blocked.value.code == "persona_source_too_large"
    assert read_sizes == [9]
