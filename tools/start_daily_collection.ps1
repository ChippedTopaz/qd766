$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Project Python missing' }
$LogRoot = Join-Path $ProjectRoot '.tmp-runtime-logs'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:NO_PROXY -ErrorAction SilentlyContinue
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $ProjectRoot
& $Python tools\run_daily_collection.py --execute *>> (Join-Path $LogRoot 'daily-collection.log')
if ($LASTEXITCODE -ne 0) { throw 'Daily run incomplete/paused; inspect checkpoint and local log' }
