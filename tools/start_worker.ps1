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
# Codex terminals can inject a temporary outbound proxy. The deployed worker
# must use the office machine's direct connection and domestic public IP.
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:NO_PROXY -ErrorAction SilentlyContinue
Set-Location -LiteralPath $RepositoryRoot
$ErrorActionPreference = "Continue"
& $Python tools\run_collection_worker.py *>> $LogFile
$workerExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($workerExitCode -ne 0) {
    throw "QD766 worker exited with code $workerExitCode"
}
