
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from rich.console import Console

from gedcom_parser.parser_core import tokenize_file
from gedcom_parser.tree_builder import build_tree
from gedcom_parser.registry.build_registry import build_registry
from gedcom_parser.registry.link_entities import link_entities
from gedcom_parser.attachments import promote_inline_media_objects

console = Console()


def load_gedcom(path: Path, *, verbose: bool = False):
    """
    Full Phase 1–4.5 pipeline runner.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    t0 = time.perf_counter()

    tokens = tokenize_file(str(path))
    tree = build_tree(tokens)
    registry = build_registry(tree)

    link_entities(registry)
    promote_inline_media_objects(registry, tree)

    elapsed = time.perf_counter() - t0

    if verbose:
        console.log(f"Loaded GEDCOM in {elapsed:.2f}s")

    return tree, registry


def write_json(
    data: Dict[str, Any],
    *,
    out: Path | None,
    pretty: bool,
):
    """
    Write JSON to stdout or file.
    """
    if pretty:
        payload = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    if out:
        out.write_text(payload, encoding="utf-8")
    else:
        print(payload)
