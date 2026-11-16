# EMS one-step updater.
# Usage (PowerShell, from anywhere):
#   powershell -ExecutionPolicy Bypass -File E:\Equipment-Management-System\EMS_Project\update.ps1 "C:\Users\<you>\Downloads\EMS_Step_B8.zip"
# It unzips the update, copies backend/ frontend/ database/ into the project, and prints the notes.
param([Parameter(Mandatory = $true)][string]$Zip)

$project = "E:\Equipment-Management-System\EMS_Project"
if (-not (Test-Path $Zip)) { Write-Host "Zip not found: $Zip" -ForegroundColor Red; exit 1 }

$temp = Join-Path $env:TEMP ("ems_update_" + [guid]::NewGuid().ToString("N"))
Expand-Archive -Path $Zip -DestinationPath $temp -Force

# the zip contains one top folder (EMS_Step_xx); go inside it
$root = Get-ChildItem $temp -Directory | Select-Object -First 1
if (-not $root) { $root = Get-Item $temp }

foreach ($part in @("backend", "frontend", "database")) {
    $src = Join-Path $root.FullName $part
    if (Test-Path $src) {
        $dest = Join-Path $project $part
        robocopy $src $dest /E /NFL /NDL /NJH /NJS /NP | Out-Null
        Write-Host "Updated $part" -ForegroundColor Green
    }
}

$notes = Join-Path $root.FullName "README.txt"
if (Test-Path $notes) { Write-Host ""; Get-Content $notes }

Remove-Item $temp -Recurse -Force
Write-Host ""
Write-Host "Done. If the notes above mention SQL, run it in pgAdmin. Then restart the backend (start_all.ps1 does both servers)." -ForegroundColor Cyan