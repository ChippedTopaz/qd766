$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$LogRoot = Join-Path $ProjectRoot '.tmp-runtime-logs'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:NO_PROXY -ErrorAction SilentlyContinue
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $ProjectRoot
& $Python tools\run_source_monitor.py --execute *>> (Join-Path $LogRoot 'source-monitor.log')
if ($LASTEXITCODE -ne 0) { throw 'Source check incomplete/paused; see admin alerts and local log. No automatic full recrawl.' }
