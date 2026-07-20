from __future__ import annotations

from pathlib import Path

import pytest
from support.persona_pack import built_pack
from test_persona_responder import MODEL, model_response, responder

from ynoy.errors import AdapterError
from ynoy.full_persona.response_context import select_response_context, select_style_signals
from ynoy.full_persona.response_protocol import citation_aliases


def test_structured_responder_rejects_exact_source_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pack = built_pack(tmp_path)[3]
    context = select_response_context(pack, "What should I do about Python?")
    selected = context[0]
    alias = citation_aliases(context, select_style_signals(pack))[selected.atom_id]

    monkeypatch.setattr(
        "ynoy.full_persona.responder.post_json",
        lambda *_args, **_kwargs: model_response([alias], response_text=selected.claim),
    )
    with pytest.raises(AdapterError) as blocked:
        responder().respond(pack, "What should I do about Python?", arm="structured")

    assert blocked.value.code == "persona_responder_source_copy"


def test_structured_responder_accepts_new_response_with_valid_citation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pack = built_pack(tmp_path)[3]
    context = select_response_context(pack, "What should I do about Python?")
    selected = context[0]
    alias = citation_aliases(context, select_style_signals(pack))[selected.atom_id]
    response_text = f"I recommend a bounded reversible step, citing {selected.atom_id}."
    monkeypatch.setattr(
        "ynoy.full_persona.responder.post_json",
        lambda *_args, **_kwargs: model_response([alias], response_text=response_text),
    )

    result = responder().respond(pack, "What should I do about Python?", arm="structured")

    assert result.response_text == response_text
    assert result.used_atom_ids == (selected.atom_id,)
    assert result.model == MODEL
