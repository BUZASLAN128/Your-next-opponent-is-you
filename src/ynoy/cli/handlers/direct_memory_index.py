from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import cast

from ynoy.cli.context import CommandContext
from ynoy.cli.direct_memory_files import load_input
from ynoy.errors import DataValidationError
from ynoy.structural_index import PreparedDocument, StructuralIndex
from ynoy.structural_index.contracts import TreeInput


def handle_index(
    args: argparse.Namespace, context: CommandContext, root: Path
) -> dict[str, object]:
    index = StructuralIndex(root, synthetic=bool(args.synthetic))
    command = args.direct_memory_command
    if command == "import-document":
        value = load_input(args.input, context, synthetic=bool(args.synthetic))
        if not isinstance(value, dict) or set(value) - {"name", "pages", "tree", "description"}:
            raise DataValidationError(
                "direct_memory_input_invalid", "Prepared bundle fields are invalid."
            )
        if not {"name", "pages", "tree"} <= set(value):
            raise DataValidationError(
                "direct_memory_input_invalid", "Prepared bundle fields are missing."
            )
        bundle = PreparedDocument(
            name=cast(str, value["name"]),
            pages=cast(list[str], value["pages"]),
            tree=cast(TreeInput, value["tree"]),
            description=cast(str | None, value.get("description")),
        )
        return asdict(index.import_document(bundle))
    if command == "list-documents":
        return {"documents": [asdict(item) for item in index.list_documents()]}
    if command == "tree":
        return {"document_id": args.document_id, "tree": index.read_tree(args.document_id)}
    if command == "read-pages":
        pages = index.read_pages(args.document_id, args.page_numbers)
        return {"pages": [asdict(page) for page in pages]}
    return {"nodes": [asdict(node) for node in index.read_nodes(args.document_id, args.node_ids)]}
