$ErrorActionPreference = "Stop"

pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\docs\generate_cli_docs.ps1
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\docs\generate_cli_reference.ps1
