$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvironmentFile = Join-Path $RepositoryRoot ".env"
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$LogDirectory = Join-Path (Split-Path -Parent $RepositoryRoot) "logs"
$LogFile = Join-Path $LogDirectory "backend.log"

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing local configuration: $EnvironmentFile"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing Python environment: $Python"
}

foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
    $value = $line.Trim()
    if (-not $value -or $value.StartsWith("#")) {
        continue
    }
    $parts = $value.Split("=", 2)
    if ($parts.Count -eq 2) {
        Set-Item -Path ("Env:" + $parts[0]) -Value $parts[1]
    }
}
Remove-Item Env:QD766_DATABASE_URL -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
Set-Location -LiteralPath $RepositoryRoot
# Uvicorn writes normal INFO messages to stderr. Windows PowerShell turns native
# stderr into error records, so a global Stop preference would kill a healthy
# server immediately. Keep the process alive and check its real exit code.
$ErrorActionPreference = "Continue"
& $Python -m uvicorn qd766.backend.main:app --host 127.0.0.1 --port 8767 --no-access-log *>> $LogFile
$backendExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($backendExitCode -ne 0) {
    throw "QD766 backend exited with code $backendExitCode"
}
