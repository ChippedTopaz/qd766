param([switch]$Confirm)
$ErrorActionPreference = 'Stop'
$TaskName = 'QD766 Worker'
$Task = Get-ScheduledTask -TaskName $TaskName
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ExpectedScript = Join-Path $PSScriptRoot 'start_controlled_worker.ps1'
if ($Task.Actions.Count -ne 1 -or $Task.Actions[0].WorkingDirectory -ne $ProjectRoot -or
    $Task.Actions[0].Arguments -notmatch [regex]::Escape($ExpectedScript)) {
    throw 'Worker action differs from reviewed configuration; no changes made.'
}
if (-not $Confirm) {
    $Task | Select-Object TaskName,State,@{Name='ExecutionTimeLimit';Expression={$_.Settings.ExecutionTimeLimit}}
    Write-Output 'CHECK_ONLY: use -Confirm to back up settings and disable the runtime limit.'
    return
}
$BackupRoot = Join-Path $ProjectRoot '.tmp-worker-task-backups'
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$BackupFile = Join-Path $BackupRoot ('worker-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.xml')
Export-ScheduledTask -TaskName $TaskName | Out-File -LiteralPath $BackupFile -Encoding utf8
$Settings = $Task.Settings
$Settings.ExecutionTimeLimit = 'PT0S'
$Settings.RestartCount = 10
$Settings.RestartInterval = 'PT1M'
Set-ScheduledTask -TaskName $TaskName -Settings $Settings | Out-Null
Write-Output ('TASK_BACKUP=' + $BackupFile)
Write-Output 'WORKER_SETTINGS=PASS; unlimited runtime; 10 failure restarts at 1-minute intervals.'
Write-Output 'Actions/principal/triggers unchanged. No task started/stopped; no database changes.'
