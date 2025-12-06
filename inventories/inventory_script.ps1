# PowerShell Inventory Script for GEDCOM Parser Project
# Save this content to a file named 'inventory_script.ps1'.
# Then open a PowerShell console (not the PS prompt), navigate to the script's folder, and run:
# .\inventory_script.ps1 -ProjectPath 'C:\Users\liqui\PyCharmProjects\GEDCOM_Parser_Project' -OutputCsv 'C:\Users\liqui\PyCharmProjects\GEDCOM_Parser_Project\file_inventory.csv'

param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectPath = 'C:\Users\liqui\PyCharmProjects\GEDCOM_Parser_Project',

    [Parameter(Mandatory = $false)]
    [string]$OutputCsv   = 'C:\Users\liqui\PyCharmProjects\GEDCOM_Parser_Project\file_inventory.csv'
)

# Resolve and validate project path
$resolvedPath = Resolve-Path -Path $ProjectPath -ErrorAction Stop
if (-not (Test-Path -Path $resolvedPath -PathType Container)) {
    Write-Error "Project path '$ProjectPath' does not exist or is not a directory."
    exit 1
}

# Gather file information recursively and export to CSV
Get-ChildItem -Path $resolvedPath -File -Recurse |
Select-Object @{Name = 'FileName';    Expression = { $_.Name }},
              @{Name = 'FullPath';    Expression = { $_.FullName }},
              @{Name = 'Directory';   Expression = { $_.DirectoryName }},
              @{Name = 'Extension';   Expression = { $_.Extension }},
              @{Name = 'SizeBytes';   Expression = { $_.Length }},
              @{Name = 'Created';     Expression = { $_.CreationTime }},
              @{Name = 'LastModified';Expression = { $_.LastWriteTime }},
              @{Name = 'Attributes';  Expression = { $_.Attributes }} |
Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding UTF8

Write-Host "File inventory exported to: $OutputCsv" -ForegroundColor Green
