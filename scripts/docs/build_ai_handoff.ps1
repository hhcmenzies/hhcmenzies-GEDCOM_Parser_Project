param(
  [string]$OutDir = "H:\",
  [string]$DocsRoot = "_docs"
)

$ErrorActionPreference = "Stop"

# Ensure running from repo root
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$timestamp = Get-Date -Format "yyyyMMdd_HHmm"
$outZip    = Join-Path $OutDir ("GEDCOM_AI_Handoff_{0}.zip" -f $timestamp)

# Roots we want included
$roots = @(
  $DocsRoot,
  "scripts\docs",
  "scripts\ops",
  "src\gedcom_parser\cli",
  "src\gedcom_parser\config.py",
  "src\gedcom_parser\DOCS_POINTER.md",
  "config",
  "datasets"
)

# Deterministic design assets folder
$assetDir = Join-Path $DocsRoot "06_handoff\_assets"
if (Test-Path $assetDir) { $roots += $assetDir }

# Optional outputs (if present)
$optional = @(
  "project_tree.txt",
  "GEDCOM_Parser_Project_inventory.csv",
  "H_drive_inventory_files.csv"
) | Where-Object { Test-Path $_ }

function Get-FilesSafe {
  param([string]$Path)

  if (-not (Test-Path $Path)) { return @() }

  $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
  if (-not $item) { return @() }

  # Skip Office lock/temp files entirely
  if (-not $item.PSIsContainer -and $item.Name -like "~$*") { return @() }

  if ($item.PSIsContainer) {
    return Get-ChildItem -LiteralPath $item.FullName -Recurse -Force -File -ErrorAction SilentlyContinue |
      Where-Object {
        $_.Name -notlike "~$*" -and
        $_.Extension -ne ".tmp" -and
        -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
      } |
      Select-Object -ExpandProperty FullName
  }

  return @($item.FullName)
}

# Build final file list (deduped)
$files = New-Object System.Collections.Generic.List[string]
foreach ($r in $roots) {
  foreach ($f in (Get-FilesSafe -Path $r)) { $files.Add($f) }
}
foreach ($p in $optional) { $files.Add((Resolve-Path $p).Path) }

$files = $files | Sort-Object -Unique

if ($files.Count -eq 0) { throw "No files found to include in handoff zip." }

Compress-Archive -Path $files -DestinationPath $outZip -Force

Write-Host "AI handoff bundle created:"
Write-Host "  $outZip"
