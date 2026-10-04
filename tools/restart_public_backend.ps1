$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot 'start_public_backend.py'
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
$TaskName = 'QD766 Public Backend'
Set-Location -LiteralPath $RepositoryRoot
$ExistingTask = Get-ScheduledTask -TaskName $TaskName
$Actions = @($ExistingTask.Actions)
if ($Actions.Count -ne 1 -or $Actions[0].Execute -ne (Join-Path $RepositoryRoot '.venv\Scripts\pythonw.exe') -or
    $Actions[0].Arguments -notmatch [regex]::Escape($Launcher)) {
    throw 'Task action differs from the reviewed public launcher. No service stopped.'
}
$ModeArguments = @()
if ($Actions[0].Arguments -match '(?:^|\s)--real-wallet(?:\s|$)') { $ModeArguments += '--real-wallet' }
if ($Actions[0].Arguments -match '(?:^|\s)--pause-paid-requests(?:\s|$)') { $ModeArguments += '--pause-paid-requests' }
& $Python $Launcher @ModeArguments --check
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
$Policy = Invoke-RestMethod -Uri 'http://127.0.0.1:8769/api/v1/access-policy' -TimeoutSec 5
$ExpectedWallet = $ModeArguments -contains '--real-wallet'
$ExpectedPause = $ModeArguments -contains '--pause-paid-requests'
if ($Policy.loginRequired -ne $true -or $Policy.inviteRequired -ne $true -or $Policy.publicReadOnly -ne $true -or
    $Policy.paidRequestsEnabled -ne $ExpectedWallet -or
    ($ExpectedWallet -and ($Policy.defaultCollectionAccess -ne $true -or $Policy.collectionRequestsPaused -ne $ExpectedPause))) {
    throw 'Public backend runtime policy differs from registered Task. Do not deploy frontend; inspect before proceeding.'
}
Write-Output ('PUBLIC_RUNTIME_POLICY=PASS REAL_WALLET=' + $ExpectedWallet + ' REQUESTS_PAUSED=' + $ExpectedPause)
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName,State
