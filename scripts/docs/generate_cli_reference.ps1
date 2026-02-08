param(
  [string]$OutFile = "_docs/02_architecture/cli_reference.md"
)

$ErrorActionPreference = "Stop"

$dt  = Get-Date -Format "yyyy-MM-dd"
$src = (git rev-parse --short HEAD)

# Capture help text
$helpMain    = (gedcom --help | Out-String).TrimEnd()
$helpDoctor  = (gedcom doctor --help | Out-String).TrimEnd()
$helpVersion = (gedcom version --help | Out-String).TrimEnd()
$helpStats   = (gedcom stats --help | Out-String).TrimEnd()
$helpExport  = (gedcom export --help | Out-String).TrimEnd()

$lines = New-Object System.Collections.Generic.List[string]
$add = { param($s) [void]$lines.Add($s) }

&$add "# CLI Reference (End-User)"
&$add ""
&$add ("_Last updated: {0}_" -f $dt)
&$add ""
&$add ("Source git commit: {0}" -f $src)
&$add ""
&$add "End-user reference for the `gedcom` CLI."
&$add ""

# Global conventions
&$add "## Global conventions"
&$add "- **Input paths**: commands that accept GEDCOM take a filesystem path."
&$add "- **Output behavior**:"
&$add "  - `stats` prints a summary to stdout."
&$add "  - `export` writes JSON to stdout by default; use `--out/-o` to write a file."
&$add "- **Exit codes**: non-zero on failure (missing file, parse error, config error)."
&$add "- **Config loading and precedence**:"
&$add "  - `processing_config.yml` is the active config (see `gedcom doctor` output)."
&$add "  - If you change config behavior, update this section to match `src/gedcom_parser/config.py`."
&$add ""

# Commands
&$add "## Commands"
&$add ""
&$add "### gedcom (top-level)"
&$add "~~~"
&$add $helpMain
&$add "~~~"
&$add ""

&$add "### doctor"
&$add "Validates environment wiring (imports, config path, expected project directories)."
&$add "~~~"
&$add $helpDoctor
&$add "~~~"
&$add ""
&$add "**Examples**"
&$add "- `gedcom doctor`"
&$add ""

&$add "### version"
&$add "Prints package version, git commit, and project root."
&$add "~~~"
&$add $helpVersion
&$add "~~~"
&$add ""
&$add "**Examples**"
&$add "- `gedcom version`"
&$add ""

&$add "### stats"
&$add "Reads a GEDCOM file and prints summary statistics."
&$add "~~~"
&$add $helpStats
&$add "~~~"
&$add ""
&$add "**Examples**"
&$add "- `gedcom stats tests/data/gedcom_1.ged`"
&$add "- `gedcom stats -v tests/data/gedcom_1.ged`"
&$add ""

&$add "### export"
&$add "Exports GEDCOM data to JSON (stdout by default)."
&$add "~~~"
&$add $helpExport
&$add "~~~"
&$add ""
&$add "**Examples**"
&$add "- `gedcom export tests/data/gedcom_1.ged > _runtime/out.json`"
&$add "- `gedcom export -o _runtime/out.json --pretty tests/data/gedcom_1.ged`"
&$add ""

# Troubleshooting
&$add "## Troubleshooting"
&$add "- **Import/module errors**: ensure the package is installed editable: `pip install -e .`"
&$add "- **Config path issues**: run `gedcom doctor` and confirm the reported `config_path` exists."
&$add "- **Encoding issues**: if a GEDCOM file fails parsing, capture the error output and record the exporter/source."
&$add ""

$lines | Set-Content $OutFile -Encoding UTF8
Write-Host ("Wrote: {0}" -f $OutFile)
