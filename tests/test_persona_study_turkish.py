# ruff: noqa: RUF001 -- Turkish dotless-i text is intentional contract evidence.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.persona_study import synthetic_codex_study_root

from ynoy.cli.main import main
from ynoy.persona_study.prepare import prepare_persona_study

_ALLOWED_VALUES = {
    "authorship": ["self", "quoted_or_pasted", "mixed", "other", "unknown"],
    "claim_holder": ["self", "assistant", "third_party", "mixed", "unknown"],
    "adoption": ["endorsed", "rejected", "hypothetical", "not_applicable", "unknown"],
    "decision": ["accept", "reject", "correct", "defer", "ask", "none", "unknown"],
    "target_layer": [
        "persona",
        "project_rule",
        "architecture",
        "mission",
        "episodic",
        "research",
        "none",
        "unknown",
    ],
    "confidence": ["high", "medium", "low", "unknown"],
    "persona_kind": [
        "trait",
        "value",
        "narrative",
        "metacognition",
        "belief",
        "preference",
        "goal",
        "relationship",
        "skill",
    ],
    "scope_risk": ["low", "medium", "high", "unknown"],
}
_LABEL_FIELDS = {
    "presentation_id",
    "authorship",
    "claim_holder",
    "adoption",
    "decision",
    "target_layer",
    "persona_kind",
    "scope",
    "rationale_spans",
    "evidence_demand_spans",
    "should_abstain",
    "exclude_from_persona",
    "exclusion_reason",
    "confidence",
    "notes",
}
_DIACRITICS = frozenset("çğıöşüÇĞİÖŞÜ")


def test_annotation_package_is_natural_turkish_without_translating_protocol_tokens(
    tmp_path: Path,
) -> None:
    source, _ = synthetic_codex_study_root(tmp_path)
    result = prepare_persona_study(source, tmp_path / "private", synthetic=True)
    template = json.loads(result.labels_path.read_text(encoding="utf-8"))
    instructions = " ".join(template["instructions"])
    review = result.review_path.read_text(encoding="utf-8")

    assert _DIACRITICS & set(instructions)
    assert all(word in instructions for word in ("yalnız", "bağımsız", "değiştirilemez"))
    assert all(token in instructions for token in ("`null`", "`user`", "`submit-labels`"))
    assert template["schema_version"] == "persona-labels/0.2"
    assert template["completed_by"] is None
    assert template["allowed_values"] == _ALLOWED_VALUES
    assert set(template["labels"][0]) == _LABEL_FIELDS

    assert review.startswith("# Özel Kişilik Etiketleme Paketi\n")
    assert all(
        phrase in review
        for phrase in ("Git dışında ve özel kalır", "bağımsız değerlendir", "Emin değilsen")
    )
    assert all(
        token in review
        for token in (
            "`labels.template.json`",
            "`authorship=self`",
            "`adoption=endorsed`",
            "`should_abstain=true`",
            "`submit-labels`",
        )
    )
    assert not any(word in review for word in ("Ozel", "bagimsiz", "degistirme", "uyusmaz"))
    for guidance in (instructions, review):
        lowered = guidance.lower()
        assert "koşullu" in lowered
        assert "opsiyonel" in lowered or "isteğe bağlı" in lowered
        assert "`null` kalabilir" in lowered or "`null` bırak" in lowered
    assert "Her boş (`null`) alanı" not in instructions
    assert "boş (`null`) alanları doldur" not in review


def test_study_cli_keeps_machine_status_and_adds_turkish_guidance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source, _ = synthetic_codex_study_root(tmp_path)
    private = tmp_path / "private"
    prepared = _run_cli(
        capsys,
        "--private-root",
        str(private),
        "study",
        "prepare",
        str(source),
        "--synthetic",
    )
    _assert_localized(prepared, "awaiting_represented_user_labels")

    status = _run_cli(
        capsys,
        "--private-root",
        str(private),
        "study",
        "status",
        str(prepared["study_id"]),
        "--synthetic",
    )
    _assert_localized(status, "awaiting_represented_user_labels")

    purge = _run_cli(
        capsys,
        "--private-root",
        str(private),
        "study",
        "purge-expired",
        "--synthetic",
    )
    _assert_localized(purge, "expired_artifacts_purged")


def _run_cli(capsys: pytest.CaptureFixture[str], *arguments: str) -> dict[str, object]:
    exit_code = main(["--indent", "0", *arguments])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0 and captured.err == "" and payload["ok"] is True
    result = payload["result"]
    assert isinstance(result, dict)
    return result


def _assert_localized(result: dict[str, object], expected_status: str) -> None:
    assert result["status"] == expected_status
    message = result["message_tr"]
    next_step = result["next_step_tr"]
    assert isinstance(message, str) and message.strip()
    assert isinstance(next_step, str) and next_step.strip()
    assert _DIACRITICS & set(f"{message} {next_step}")
