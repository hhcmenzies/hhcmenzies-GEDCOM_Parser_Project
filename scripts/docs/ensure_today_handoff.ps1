param(
  [string]$DocsRoot = "_docs"
)

$ErrorActionPreference = "Stop"

$dt = Get-Date -Format "yyyy-MM-dd"
$path = Join-Path $DocsRoot ("06_handoff/{0}.md" -f $dt)

New-Item -ItemType Directory -Force (Split-Path $path) | Out-Null

if (-not (Test-Path $path)) {
@"
# Handoff

## Date
$dt

## Run / Branch / Commit
- Branch: $(git branch --show-current)
- Commit: $(git rev-parse --short HEAD)

## What Changed
-

## What Was Decided
-

## Current Blockers
-

## Next Actions (Ordered)
1.
2.
3.

## Notes for Next Chat
-
"@ | Set-Content -Encoding UTF8 $path
}

Write-Host "Ensured handoff file:"
Write-Host "  $path"
