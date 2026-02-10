param(
  [string]$Root = "H:\",
  [string]$OutCsv = "H:\H_drive_inventory_files.csv"
)

$ErrorActionPreference = "Stop"

# Ensure output directory exists
$parent = Split-Path $OutCsv
if ($parent -and -not (Test-Path $parent)) {
  New-Item -ItemType Directory -Force $parent | Out-Null
}

# Full drive file inventory (can be slow)
Get-ChildItem -LiteralPath $Root -Recurse -Force -File -ErrorAction SilentlyContinue |
  Select-Object @{
      Name="FullName"; Expression={$_.FullName}
    }, @{
      Name="DirectoryName"; Expression={$_.DirectoryName}
    }, @{
      Name="Name"; Expression={$_.Name}
    }, @{
      Name="Extension"; Expression={$_.Extension}
    }, @{
      Name="LengthBytes"; Expression={$_.Length}
    }, @{
      Name="LastWriteTime"; Expression={$_.LastWriteTime}
    }, @{
      Name="CreationTime"; Expression={$_.CreationTime}
    }, @{
      Name="Attributes"; Expression={$_.Attributes.ToString()}
    } |
  Export-Csv -NoTypeInformation -Encoding UTF8 $OutCsv

Write-Host "Wrote:"
Write-Host "  $OutCsv"
