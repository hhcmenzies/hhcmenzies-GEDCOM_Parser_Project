from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from gedcom_parser.cli.utils import load_gedcom, write_json

console = Console()


def export_command(
    gedcom: Path = typer.Argument(..., exists=True, readable=True),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Write output to file instead of stdout",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable rich logging",
    ),
):
    """
    Export GEDCOM data to JSON (stdout by default).
    """
    tree, registry = load_gedcom(gedcom, verbose=verbose)

    data = {
        "counts": {
            "individuals": len(registry.individuals),
            "families": len(registry.families),
            "sources": len(registry.sources),
            "notes": len(registry.notes),
            "media_objects": len(registry.media_objects),
        },
        "individuals": [
            ind.__dict__ for ind in registry.individuals.values()
        ],
        "families": [
            fam.__dict__ for fam in registry.families.values()
        ],
        "sources": [
            src.__dict__ for src in registry.sources.values()
        ],
        "notes": [
            note.__dict__ for note in registry.notes.values()
        ],
        "media_objects": [
            mo.__dict__ for mo in registry.media_objects.values()
        ],
    }

    if verbose:
        console.log("Exporting JSON")

    write_json(data, out=out, pretty=pretty)

    if verbose:
        console.log("Export complete")

