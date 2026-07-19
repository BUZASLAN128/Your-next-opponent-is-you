from __future__ import annotations

import json
from pathlib import Path

from support.persona_pack import built_pack

from ynoy.cli.context import CommandContext
from ynoy.cli.handlers.study_full_persona_dossier import profile_full_persona
from ynoy.cli.parser import parse_args
from ynoy.config import Settings
from ynoy.full_persona.pack_store import FullPersonaPackStore


def test_profile_full_persona_parser_and_handler_are_stdout_only(tmp_path: Path) -> None:
    _, private_root, _, pack = built_pack(tmp_path)
    store = FullPersonaPackStore(private_root, synthetic=True)
    store.write_pack(pack)
    before = sorted(
        path.relative_to(store.run_path(pack.run_id)).as_posix()
        for path in store.run_path(pack.run_id).rglob("*")
    )

    args = parse_args(["study", "profile-full-persona", pack.run_id, "--synthetic"])
    assert args.study_command == "profile-full-persona"
    context = CommandContext(
        settings=Settings.from_environment(private_root=private_root),
        repository_root=tmp_path,
    )
    result = profile_full_persona(args, context)

    assert tuple(item["key"] for item in result["topics"]) == (
        "birth",
        "childhood",
        "education",
        "exams",
        "work_projects",
        "knowledge",
        "skills",
        "values",
        "goals",
        "decision_behavior",
        "risk_boundaries",
        "relationships",
        "contradictions",
        "response_style",
    )
    assert result["pack_id"] == pack.pack_id
    assert result["persistent"] is False
    assert result["persona_quality_claimed"] is False
    encoded = json.dumps(result, default=str)
    assert str(private_root) not in encoded
    after = sorted(
        path.relative_to(store.run_path(pack.run_id)).as_posix()
        for path in store.run_path(pack.run_id).rglob("*")
    )
    assert before == after
