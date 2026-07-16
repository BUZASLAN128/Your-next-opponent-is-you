from __future__ import annotations

import json
from zipfile import ZipFile

from ynoy.errors import DataValidationError


def assert_synthetic_marker(archive: ZipFile) -> None:
    marker_name = "ynoy-synthetic-fixture.json"
    matches = [info for info in archive.infolist() if info.filename == marker_name]
    if len(matches) != 1 or matches[0].file_size > 1024:
        raise DataValidationError(
            "synthetic_fixture_marker_required",
            "A D0 ChatGPT fixture needs one bounded ynoy-synthetic-fixture.json marker.",
        )
    try:
        with archive.open(matches[0]) as stream:
            marker = json.loads(stream.read(1025).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataValidationError(
            "synthetic_fixture_marker_invalid", "Synthetic fixture marker is invalid."
        ) from exc
    if marker != {"schema_version": "1.0", "synthetic": True}:
        raise DataValidationError(
            "synthetic_fixture_marker_invalid", "Synthetic fixture marker is invalid."
        )
