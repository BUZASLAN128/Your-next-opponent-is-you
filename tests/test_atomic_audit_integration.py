from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import synthetic_audit

from ynoy.bootstrap import load_bootstrap
from ynoy.corpus import ChatGPTZipAdapter
from ynoy.errors import StorageError
from ynoy.models import BootstrapDeclaration, CandidateKind, DataClass
from ynoy.storage import (
    AuditRepository,
    CorpusRepository,
    Database,
    MemoryMutationRepository,
)

pytestmark = pytest.mark.integration


def _load_unique_bootstrap(tmp_path: Path, statement: str):
    source = tmp_path / f"bootstrap-{uuid4()}.json"
    source.write_text(
        json.dumps([{"statement": statement, "synthetic": True}]),
        encoding="utf-8",
    )
    return load_bootstrap(source, synthetic=True)


def _scalar(database: Database, query: str, parameters: tuple[object, ...]) -> object:
    with database.connect() as connection:
        row = connection.execute(query, parameters).fetchone()
    assert row is not None
    return row["value"]


def test_invalid_audit_rolls_back_inventory_mutation(
    test_database: Database, make_chatgpt_zip
) -> None:
    manifest = ChatGPTZipAdapter().inventory(make_chatgpt_zip(), synthetic=True)
    invalid_audit = synthetic_audit(event_type="inventory").model_copy(update={"record_id": None})
    with pytest.raises(StorageError):
        CorpusRepository(test_database).save_inventory(manifest, invalid_audit)
    count = _scalar(
        test_database,
        "SELECT count(*) AS value FROM ynoy.inventory_manifests WHERE record_id = %s",
        (manifest.record_id,),
    )
    assert count == 0


def test_duplicate_audit_rolls_back_bootstrap_source_and_declarations(
    test_database: Database, tmp_path: Path
) -> None:
    declarations = _load_unique_bootstrap(tmp_path, f"atomic bootstrap declaration {uuid4()}")
    duplicate_audit = synthetic_audit(reason_code="duplicate_bootstrap_audit")
    AuditRepository(test_database).append(duplicate_audit)
    with pytest.raises(StorageError):
        MemoryMutationRepository(test_database).add_bootstrap_declarations(
            declarations, duplicate_audit
        )
    source_count = _scalar(
        test_database,
        "SELECT count(*) AS value FROM ynoy.bootstrap_sources WHERE record_id = %s",
        (declarations[0].source_record_id,),
    )
    declaration_count = _scalar(
        test_database,
        "SELECT count(*) AS value FROM ynoy.bootstrap_declarations WHERE source_record_id = %s",
        (declarations[0].source_record_id,),
    )
    assert source_count == 0 and declaration_count == 0


def test_duplicate_audit_rolls_back_correction_and_replacement(
    test_database: Database, tmp_path: Path
) -> None:
    declarations = _load_unique_bootstrap(tmp_path, f"atomic correction target {uuid4()}")
    mutations = MemoryMutationRepository(test_database)
    mutations.add_bootstrap_declarations(declarations, synthetic_audit())
    replacement = BootstrapDeclaration(
        kind=CandidateKind.PREFERENCE,
        statement=f"replacement {uuid4()}",
        source_name="atomic-replacement.json",
        data_class=DataClass.PUBLIC_SYNTHETIC,
        synthetic=True,
    )
    duplicate_audit = synthetic_audit(reason_code="duplicate_correction_audit")
    AuditRepository(test_database).append(duplicate_audit)
    with pytest.raises(StorageError):
        mutations.correct(
            target_record_id=declarations[0].record_id,
            reason="must roll back",
            audit_receipt=duplicate_audit,
            replacement=replacement,
        )
    with test_database.connect() as connection:
        state = connection.execute(
            """
            SELECT
              (SELECT status FROM ynoy.bootstrap_declarations
               WHERE record_id = %s) AS target_status,
              (SELECT count(*) FROM ynoy.memory_corrections
               WHERE target_record_id = %s) AS corrections,
              (SELECT count(*) FROM ynoy.bootstrap_declarations
               WHERE record_id = %s) AS replacements,
              (SELECT count(*) FROM ynoy.bootstrap_sources
               WHERE record_id = %s) AS replacement_sources
            """,
            (
                declarations[0].record_id,
                declarations[0].record_id,
                replacement.record_id,
                replacement.source_record_id,
            ),
        ).fetchone()
    assert state is not None
    assert state["target_status"] == "confirmed"
    assert state["corrections"] == 0
    assert state["replacements"] == 0 and state["replacement_sources"] == 0
