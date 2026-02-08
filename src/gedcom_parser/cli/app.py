from __future__ import annotations

import typer
from rich.console import Console

from gedcom_parser.cli.commands.doctor import doctor_command
from gedcom_parser.cli.commands.export import export_command
from gedcom_parser.cli.commands.stats import stats_command
from gedcom_parser.cli.commands.version import version_command

app = typer.Typer(
    name="gedcom",
    help="GEDCOM parser, inspector, and exporter",
    add_completion=False,
)

console = Console()

app.command("doctor")(doctor_command)
app.command("version")(version_command)
app.command("export")(export_command)
app.command("stats")(stats_command)


def main():
    app()


if __name__ == "__main__":
    main()
