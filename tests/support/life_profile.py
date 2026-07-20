# ruff: noqa: RUF001 -- Turkish identity evidence is intentional.

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from support.full_persona import canonical_file
from support.persona_study import synthetic_codex_study_root
from ynoy.full_persona.manifest import freeze_full_corpus
from ynoy.full_persona.scan import scan_full_corpus
from ynoy.full_persona.store import FullPersonaStore
from ynoy.persona_study.prepare import PreparedPersonaStudy, prepare_persona_study
from ynoy.util import utc_now

LIFE_PROFILE_EVIDENCE = (
    "02-01-1990 tarihinde doğdum.",
    "Çocukken Ankara'da büyüdüm.",
    "Üniversitede bilgisayar mühendisliği okudum.",
    "YKS'ye girdim ve puanım yüksekti.",
    "Şu anda 32 yaşındayım.",
)
LIFE_PROFILE_EXPECTED_FACTS = (
    "02-01-1990 tarihinde doğdum",
    "Çocukken Ankara'da büyüdüm",
    "Üniversitede bilgisayar mühendisliği okudum",
    "YKS'ye girdim ve puanım yüksekti",
    "32 yaşındayım",
)
LIFE_PROFILE_FALSE_POSITIVES = (
    "Oğlum, bugün hava güzel.",
    "Arkadaşım, yarın görüşürüz.",
    "Sınav hakkında bugün not aldım.",
    "# context from my IDE setup:\nÜniversitede bilgisayar mühendisliği okudum.",
)


def prepared_life_profile_source(
    tmp_path: Path,
    *,
    include_life_evidence: bool = True,
) -> tuple[Path, Path, PreparedPersonaStudy, str]:
    source_root, _ = synthetic_codex_study_root(tmp_path)
    _append_user_evidence(source_root, include_life_evidence=include_life_evidence)
    private_root = tmp_path / "private"
    prepared = prepare_persona_study(
        source_root,
        private_root,
        synthetic=True,
        evaluation_time=utc_now(),
    )
    manifest = freeze_full_corpus(
        source_root,
        private_root,
        prepared.manifest.study_id,
        synthetic=True,
    )
    store = FullPersonaStore(private_root, synthetic=True)
    store.write_manifest(manifest)
    head = scan_full_corpus(source_root, private_root, manifest.run_id, synthetic=True)
    assert head.status == "complete"
    return source_root, private_root, prepared, manifest.run_id


def _append_user_evidence(source_root: Path, *, include_life_evidence: bool) -> None:
    path = canonical_file(source_root, 0)
    values = (
        *(LIFE_PROFILE_EVIDENCE if include_life_evidence else ()),
        *LIFE_PROFILE_FALSE_POSITIVES,
    )
    with path.open("a", encoding="utf-8") as stream:
        for minute, text in enumerate(values, start=20):
            payload = {
                "type": "response_item",
                "timestamp": f"2026-01-01T03:{minute:02d}:00+00:00",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    stable_ns = int(datetime(2026, 1, 1, 3, 4, 5, tzinfo=UTC).timestamp() * 1_000_000_000)
    os.utime(path, ns=(stable_ns, stable_ns))
