
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from gedcom_parser.cli.utils import load_gedcom

console = Console()


def stats_command(
    gedcom: Path = typer.Argument(..., exists=True, readable=True),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable rich logging",
    ),
):
    """
    Show summary statistics for a GEDCOM file.
    """
    _, registry = load_gedcom(gedcom, verbose=verbose)

    table = Table(title="GEDCOM Statistics")
    table.add_column("Entity", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Individuals", str(len(registry.individuals)))
    table.add_row("Families", str(len(registry.families)))
    table.add_row("Sources", str(len(registry.sources)))
    table.add_row("Notes", str(len(registry.notes)))
    table.add_row("Media Objects", str(len(registry.media_objects)))

    console.print(table)
