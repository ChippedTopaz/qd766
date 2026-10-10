param([switch]$Confirm)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$TaskName = 'QD766 Worker'
$Task = Get-ScheduledTask -TaskName $TaskName
$ExpectedScript = Join-Path $PSScriptRoot 'start_controlled_worker.ps1'
if ($Task.Actions.Count -ne 1 -or $Task.Actions[0].WorkingDirectory -ne $ProjectRoot -or
    $Task.Actions[0].Arguments -notmatch [regex]::Escape($ExpectedScript)) {
    throw 'Unexpected worker action; nothing stopped.'
}
if (-not $Confirm) {
    & $Python (Join-Path $PSScriptRoot 'check_collection_worker_health.py')
    if ($LASTEXITCODE -ne 0) { throw 'Worker health check failed.' }
    Write-Output 'CHECK_ONLY: use -Confirm for an idle-only worker restart.'
    return
}
Push-Location -LiteralPath $ProjectRoot
try {
    # Import-only preflight; no schema migration, upstream calls or wallet edits.
    @'
import sys
sys.path.insert(0,'src')
from qd766.backend.jobs import renew_worker_lease, owned_worker_job
from qd766.backend.worker import run_one_job
from qd766.concurrent_collection import PooledHttpTransport
print('WORKER_IMPORTS=PASS')
'@ | & $Python -
    if ($LASTEXITCODE -ne 0) { throw 'Worker imports failed; nothing stopped.' }
    $Health = (& $Python (Join-Path $PSScriptRoot 'check_collection_worker_health.py')) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $Health.status -ne 'IDLE' -or $null -ne $Health.leaseAgeSeconds) {
        throw 'Collection is not idle or another collector owns the lease. Retry after current work finishes.'
    }
    $BackupRoot = Join-Path $ProjectRoot ('.tmp-worker-task-backups\restart-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $BackupRoot | Out-Null
    Export-ScheduledTask -TaskName $TaskName | Out-File -LiteralPath (Join-Path $BackupRoot 'worker-task.xml') -Encoding utf8
    # Capture exact identities BEFORE stopping the wrapper; no broad Python kill.
    $WorkerProcesses = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'run_collection_worker\.py(?:"|\s|$)' -and
        $_.CommandLine -match [regex]::Escape($Python)
    })
    foreach ($Process in $WorkerProcesses) {
        if ($Process.CommandLine -notmatch '(?:^|\s)--controlled(?:\s|$)') {
            throw 'Unexpected worker process mode; nothing stopped.'
        }
    }
    $Settings = $Task.Settings
    $Settings.ExecutionTimeLimit = 'PT0S'
    $Settings.RestartCount = 10
    $Settings.RestartInterval = 'PT1M'
    Set-ScheduledTask -TaskName $TaskName -Settings $Settings | Out-Null
    # Check once more immediately before stop. Never intentionally interrupt a job.
    $Health = (& $Python (Join-Path $PSScriptRoot 'check_collection_worker_health.py')) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $Health.status -ne 'IDLE' -or $null -ne $Health.leaseAgeSeconds) {
        throw 'Work arrived; restart deferred. Settings hardened, current work untouched.'
    }
    Stop-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    foreach ($Process in $WorkerProcesses) {
        $Current = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $Process.ProcessId)
        if ($Current -and $Current.ExecutablePath -eq $Process.ExecutablePath -and $Current.CommandLine -eq $Process.CommandLine) {
            Stop-Process -Id $Current.ProcessId -ErrorAction Stop
        } elseif ($Current) { throw 'PID identity changed; inspect worker before restarting.' }
    }
    # Refuse to launch if an unmatched old process could still consume the queue.
    $Remaining = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'run_collection_worker\.py(?:"|\s|$)' -and
        $_.CommandLine -match [regex]::Escape($Python)
    })
    if ($Remaining.Count) { throw 'Old worker remains; no duplicate process started.' }
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 5
    $UpdatedTask = Get-ScheduledTask -TaskName $TaskName
    if ($UpdatedTask.State -ne 'Running') { throw 'Worker did not remain running; inspect controlled-worker.log.' }
    Write-Output ('TASK_BACKUP=' + $BackupRoot)
    Write-Output 'WORKER_RESTART=PASS'
    $UpdatedTask | Select-Object TaskName,State,@{Name='ExecutionTimeLimit';Expression={$_.Settings.ExecutionTimeLimit}}
    & $Python (Join-Path $PSScriptRoot 'check_collection_worker_health.py')
    if ($LASTEXITCODE -ne 0) { throw 'Worker started but health requires inspection.' }
    Write-Output 'Backend/frontend/schema/Credit/daily schedule unchanged.'
} finally { Pop-Location }
