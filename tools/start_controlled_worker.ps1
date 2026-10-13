param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Project Python missing' }
$LogRoot = Join-Path $ProjectRoot '.tmp-runtime-logs'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:NO_PROXY -ErrorAction SilentlyContinue
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $ProjectRoot
$WorkerScript = Join-Path $ProjectRoot 'tools\run_collection_worker.py'
$WorkerLog = Join-Path $LogRoot 'controlled-worker.log'
if ($CheckOnly) {
    & $Python -c "import sys; sys.path.insert(0,'src'); from qd766.backend.worker import run_one_job; from qd766.backend.jobs import requeue_expired_jobs; from qd766.concurrent_collection import PooledHttpTransport; print('WORKER_SUPERVISOR_IMPORTS=PASS')"
    if ($LASTEXITCODE -ne 0) { throw 'Worker imports failed.' }
    Write-Output 'CHECK_ONLY: no process started; no database/provider/Credit/task changes.'
    return
}
# Never stop or reset an active collection. The existing PostgreSQL lease
# serializes jobs and safely requeues expired running jobs on a new child.
$FailureCount = 0
while ($true) {
    $StartedAt = Get-Date
    $ExitCode = -1
    @{ event='worker-supervisor-start'; at=$StartedAt.ToUniversalTime().ToString('o'); wrapperPid=$PID } |
        ConvertTo-Json -Compress | Out-File -LiteralPath $WorkerLog -Append -Encoding utf8
    try {
        & $Python $WorkerScript --controlled *>> $WorkerLog
        $ExitCode = $LASTEXITCODE
    } catch {
        # Do not log exception bodies, environment settings or SQL parameters.
        @{ event='worker-supervisor-error'; at=(Get-Date).ToUniversalTime().ToString('o'); errorType=$_.Exception.GetType().Name } |
            ConvertTo-Json -Compress | Out-File -LiteralPath $WorkerLog -Append -Encoding utf8
    }
    if (((Get-Date) - $StartedAt).TotalSeconds -ge 60) { $FailureCount = 0 }
    $FailureCount++
    $Delay = [int][Math]::Min(60, 5 * [Math]::Pow(2, [Math]::Min($FailureCount - 1, 4)))
    @{ event='worker-supervisor-restart'; at=(Get-Date).ToUniversalTime().ToString('o'); exitCode=$ExitCode; delaySeconds=$Delay } |
        ConvertTo-Json -Compress | Out-File -LiteralPath $WorkerLog -Append -Encoding utf8
    Start-Sleep -Seconds $Delay
}
