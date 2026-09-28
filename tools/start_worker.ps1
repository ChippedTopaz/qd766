$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvironmentFile = Join-Path $RepositoryRoot ".env"
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$LogDirectory = Join-Path (Split-Path -Parent $RepositoryRoot) "logs"
$LogFile = Join-Path $LogDirectory "worker.log"

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing local configuration: $EnvironmentFile"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing Python environment: $Python"
}

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
Set-Location -LiteralPath $RepositoryRoot
& $Python tools\run_collection_worker.py *>> $LogFile
