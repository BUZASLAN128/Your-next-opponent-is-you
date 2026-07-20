from __future__ import annotations

import json
from typing import Any

import pytest
from support.persona_pack import built_pack

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.study_full_persona_responder import respond_full_persona
from ynoy.cli.parser import parse_args
from ynoy.config import Settings
from ynoy.full_persona.pack_store import FullPersonaPackStore

MODEL = "ynoy-persona-fixture"
REVISION = "fixture-r1"
MODEL_SHA = "a" * 64


def model_response() -> dict[str, object]:
    candidate = {
        "response_text": "Synthetic bounded response.",
        "used_atom_ids": [],
        "uncertainties": ["synthetic fixture; not calibrated"],
        "should_abstain": True,
    }
    return {
        "model": MODEL,
        "choices": [{"message": {"content": json.dumps(candidate)}}],
    }


@pytest.mark.parametrize("arm", ["structured", "generic"])
def test_respond_full_persona_cli_parser_and_handler_are_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, arm: str
) -> None:
    _, private_root, _, pack = built_pack(tmp_path)
    FullPersonaPackStore(private_root, synthetic=True).write_pack(pack)
    monkeypatch.setenv("YNOY_LOCAL_REASONER_URL", "http://127.0.0.1:18100/v1/chat/completions")
    monkeypatch.setenv("YNOY_LOCAL_MODEL_ATTESTED", "true")
    monkeypatch.setenv("YNOY_LOCAL_REASONER_MODEL", MODEL)
    monkeypatch.setenv("YNOY_LOCAL_REASONER_REVISION", REVISION)
    monkeypatch.setenv("YNOY_LOCAL_REASONER_ARTIFACT_SHA256", MODEL_SHA)

    args = parse_args(
        [
            "study",
            "respond-full-persona",
            pack.source_run_id,
            "What should I do about Python?",
            "--arm",
            arm,
            "--synthetic",
        ]
    )
    assert args.study_command == "respond-full-persona"
    assert args.arm == arm
    with pytest.raises(SystemExit):
        parse_args(["study", "respond-full-persona", pack.source_run_id, "query", "--send"])

    def transport(_: str, payload: dict[str, object], **__: object) -> dict[str, object]:
        content = json.loads(payload["messages"][1]["content"])
        aliases = [item["atom_id"] for item in content["persona_observations"]]
        raw = model_response()
        candidate = json.loads(raw["choices"][0]["message"]["content"])
        candidate["used_atom_ids"] = aliases[:1] if arm == "structured" else []
        raw["choices"][0]["message"]["content"] = json.dumps(candidate)
        return raw

    monkeypatch.setattr("ynoy.full_persona.responder.post_json", transport)
    context = CommandContext(
        settings=Settings.from_environment(private_root=private_root),
        repository_root=tmp_path,
    )
    result = respond_full_persona(args, context)
    assert result["judgment_basis"] == "abstention"
    assert result["authority"] == "none"
    assert result["action_status"] == "not_performed"
    assert result["send_enabled"] is False
    assert result["execute_enabled"] is False
    assert all("private_root" not in key and "source_root" not in key for key in result)
    assert str(private_root) not in json.dumps(result, default=str)
