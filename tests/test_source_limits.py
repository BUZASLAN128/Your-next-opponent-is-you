from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_source_modularity_checker_is_part_of_pytest() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check-source-limits.py")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Source modularity gate passed." in result.stdout
