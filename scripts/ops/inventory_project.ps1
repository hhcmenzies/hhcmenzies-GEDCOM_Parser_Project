param(
  [string]$ProjectRoot = "H:\Projects\GEDCOM_Parser_Project",
  [string]$OutCsv = "H:\Projects\GEDCOM_Parser_Project\GEDCOM_Parser_Project_inventory.csv",
  [string]$OutTree = "H:\Projects\GEDCOM_Parser_Project\project_tree.txt"
)

$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

# Project inventory (files + dirs)
Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force -ErrorAction SilentlyContinue |
  Select-Object @{
      Name="FullName"; Expression={$_.FullName}
    }, @{
      Name="Type"; Expression={ if ($_.PSIsContainer) { "Dir" } else { "File" } }
    }, @{
      Name="LengthBytes"; Expression={ if ($_.PSIsContainer) { $null } else { $_.Length } }
    }, LastWriteTime, CreationTime, Attributes |
  Export-Csv -NoTypeInformation -Encoding UTF8 $OutCsv

# Readable tree
cmd /c "tree /A /F" > $OutTree

Write-Host "Wrote:"
Write-Host "  $OutCsv"
Write-Host "  $OutTree"
