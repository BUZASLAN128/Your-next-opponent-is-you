from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from pathlib import Path

MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 50
MAX_CLASS_LINES = 200
ROOT = Path(__file__).resolve().parents[1]


def source_files() -> Iterable[Path]:
    for directory in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        if not directory.exists():
            continue
        yield from sorted(
            path for path in directory.rglob("*.py") if "__pycache__" not in path.parts
        )
    script_root = ROOT / "scripts"
    if script_root.exists():
        yield from sorted(script_root.rglob("*.sql"))
    migration_root = ROOT / "src" / "ynoy" / "migrations"
    if migration_root.exists():
        yield from sorted(migration_root.glob("*.sql"))


def span(node: ast.AST) -> int:
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", start)
    return int(end) - int(start) + 1


def inspect_python(path: Path) -> list[str]:
    failures: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return [f"{path}: cannot inspect source: {exc.__class__.__name__}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            node_span = span(node)
            if node_span > MAX_FUNCTION_LINES:
                failures.append(
                    f"{path}:{node.lineno} function {node.name} has {node_span} lines "
                    f"(max {MAX_FUNCTION_LINES})"
                )
        elif isinstance(node, ast.ClassDef):
            node_span = span(node)
            if node_span > MAX_CLASS_LINES:
                failures.append(
                    f"{path}:{node.lineno} class {node.name} has {node_span} lines "
                    f"(max {MAX_CLASS_LINES})"
                )
    return failures


def main() -> int:
    failures: list[str] = []
    for path in source_files():
        try:
            line_count = len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(f"{path}: cannot count source: {exc.__class__.__name__}")
            continue
        if line_count > MAX_FILE_LINES:
            failures.append(f"{path}: has {line_count} lines (max {MAX_FILE_LINES})")
        if path.suffix == ".py":
            failures.extend(inspect_python(path))
    if failures:
        print("Source modularity gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Source modularity gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
