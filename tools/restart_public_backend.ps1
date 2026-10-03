$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot 'start_public_backend.py'
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
$TaskName = 'QD766 Public Backend'
Set-Location -LiteralPath $RepositoryRoot
& $Python $Launcher --check
if ($LASTEXITCODE -ne 0) { throw 'Configuration invalid; current server was NOT stopped.' }
Stop-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2
# Old wrapper tasks may leave their Python child alive. Verify its full launcher
# path before stopping only the listener on this one port. Never kill all Python.
$Listeners = @(Get-NetTCPConnection -LocalPort 8769 -State Listen -ErrorAction SilentlyContinue)
foreach ($Listener in $Listeners) {
    $ServerProcess = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $Listener.OwningProcess)
    if (-not $ServerProcess -or $ServerProcess.Name -notin @('python.exe','pythonw.exe') -or
        $ServerProcess.CommandLine -notmatch [regex]::Escape($Launcher)) {
        throw 'Port 8769 is owned by an unverified process. No process killed; inspect it manually.'
    }
    Stop-Process -Id $ServerProcess.ProcessId
    Write-Output ('OLD_PUBLIC_PROCESS_STOPPED=' + $ServerProcess.ProcessId)
}
Start-Sleep -Seconds 1
if (Get-NetTCPConnection -LocalPort 8769 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8769 is still occupied; no second server started.'
}
Start-ScheduledTask -TaskName $TaskName
$Ready = $false
for ($Attempt = 0; $Attempt -lt 10; $Attempt++) {
    Start-Sleep -Seconds 1
    try {
        $Response = Invoke-RestMethod -Uri 'http://127.0.0.1:8769/api/v1/health/ready' -TimeoutSec 3
        if ($Response.status -eq 'ok') { $Ready = $true; break }
    } catch { }
}
if (-not $Ready) { throw 'Public backend not ready. Inspect .tmp-public-logs/public-backend-v2.log and task state.' }
Write-Output 'PUBLIC_BACKEND_READY=ok'
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName,State
