$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$LogDirectory = Join-Path (Split-Path -Parent $RepositoryRoot) "logs"
$LogFile = Join-Path $LogDirectory "national-summary.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing Python environment: $Python"
}

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:NO_PROXY -ErrorAction SilentlyContinue
Set-Location -LiteralPath $RepositoryRoot
$env:PYTHONUTF8 = "1"
Add-Content -LiteralPath $LogFile -Value ("RUN_STARTED=" + (Get-Date).ToString("o")) -Encoding UTF8
$ErrorActionPreference = "Continue"
& $Python tools\refresh_national_summaries.py *>> $LogFile
$refreshExitCode = $LASTEXITCODE
Add-Content -LiteralPath $LogFile -Value ("RUN_FINISHED=" + (Get-Date).ToString("o") + " EXIT_CODE=" + $refreshExitCode) -Encoding UTF8
$ErrorActionPreference = "Stop"
if ($refreshExitCode -ne 0) {
    throw "QD766 national summary refresh exited with code $refreshExitCode"
}
