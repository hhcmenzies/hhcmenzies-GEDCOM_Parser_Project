param(
  [string]$OutDir = "_docs/02_architecture"
)

$ErrorActionPreference = "Stop"

# Ensure output dir exists
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$dt  = Get-Date -Format "yyyy-MM-dd"
$src = (git rev-parse --short HEAD)

# Helper list + add fn
$lines = New-Object System.Collections.Generic.List[string]
$add = { param($s) [void]$lines.Add($s) }

# ---------- cli_modules_snapshot.md ----------
$lines.Clear()

&$add "# CLI Modules & Command Surface (Generated Snapshot)"
&$add ""
&$add ("_Last updated: {0}_" -f $dt)
&$add ""
&$add ""
&$add "This snapshot is generated from the current source tree and CLI help output. Regenerate after any CLI change."
&$add ""

# A) CLI help output
&$add "## A) CLI help output"
&$add ""

&$add "### gedcom --help"
&$add "~~~"
&$add ((gedcom --help | Out-String).TrimEnd())
&$add "~~~"
&$add ""

foreach ($cmd in @('doctor','version','stats','export')) {
  &$add ("### gedcom {0} --help" -f $cmd)
  &$add "~~~"
  &$add ((gedcom $cmd --help | Out-String).TrimEnd())
  &$add "~~~"
  &$add ""
}

# B) CLI implementation inventory
&$add "## B) CLI implementation file inventory"
&$add ""
&$add "~~~"
$paths = Get-ChildItem -Recurse src\gedcom_parser\cli -File |
  Sort-Object FullName |
  Select-Object -ExpandProperty FullName
&$add ($paths -join "`n")
&$add "~~~"
&$add ""

# C) Typer wiring
&$add "## C) Command registration (Typer wiring references)"
&$add ""
&$add "~~~"
$hits = Select-String -Path "src\gedcom_parser\cli\**\*.py" -Pattern @(
  "add_typer", "Typer(", ".command("
) -SimpleMatch | ForEach-Object {
  "{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()
}
&$add ($hits -join "`n")
&$add "~~~"
&$add ""

# D) Config references
&$add "## D) Config entrypoints referenced by parser/CLI"
&$add ""
&$add "~~~"
$cfgHits = Select-String -Path "src\gedcom_parser\**\*.py" -Pattern @(
  "get_config", "processing_config.yml", "gedcom_parser.yml"
) -SimpleMatch | ForEach-Object {
  "{0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()
}
&$add ($cfgHits -join "`n")
&$add "~~~"
&$add ""

$target1 = Join-Path $OutDir "cli_modules_snapshot.md"
$lines | Set-Content $target1 -Encoding UTF8

# ---------- cli_inventory.md (help + module map) ----------
$inv = New-Object System.Collections.Generic.List[string]
$invAdd = { param($s) [void]$inv.Add($s) }

&$invAdd "# CLI Inventory (Current Surface)"
&$invAdd ""
&$invAdd ("_Last updated: {0}_" -f $dt)
&$invAdd ""
&$invAdd "This document is the authoritative snapshot of the current CLI surface and its module mapping."
&$invAdd ""
&$invAdd "## A) CLI help (generated)"
&$invAdd ""
&$invAdd ""

$help = (gedcom --help | Out-String).TrimEnd()
&$invAdd "~~~"
&$invAdd $help
&$invAdd "~~~"
&$invAdd ""

foreach ($cmd in @('stats','export','doctor','version')) {
  $out = (gedcom $cmd --help | Out-String).TrimEnd()
  &$invAdd ("## Command: {0}" -f $cmd)
  &$invAdd ""
  &$invAdd "~~~"
  &$invAdd $out
  &$invAdd "~~~"
  &$invAdd ""
}

&$invAdd "## B) Module map (implementation)"
&$invAdd ""
$paths2 = Get-ChildItem -Recurse src\gedcom_parser\cli -File | Sort-Object FullName | Select-Object -ExpandProperty FullName
&$invAdd "~~~"
&$invAdd ($paths2 -join "`n")
&$invAdd "~~~"
&$invAdd ""

$target2 = Join-Path $OutDir "cli_inventory.md"
$inv | Set-Content $target2 -Encoding UTF8

Write-Host "Generated:"
Write-Host " - $target1"
Write-Host " - $target2"
Write-Host ("Source commit: {0}" -f $src)
