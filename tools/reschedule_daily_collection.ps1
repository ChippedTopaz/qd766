param([switch]$Confirm)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([TimeZoneInfo]::Local.BaseUtcOffset.TotalHours -ne 7) { throw 'Host must use Vietnam UTC+07:00' }
$Task = Get-ScheduledTask -TaskName 'QD766 Daily Collection'
$Actions = @($Task.Actions)
$ExpectedScript = Join-Path $PSScriptRoot 'start_daily_collection.ps1'
if ($Actions.Count -ne 1 -or $Actions[0].WorkingDirectory -ne $ProjectRoot -or
    -not $Actions[0].Arguments.Contains($ExpectedScript)) { throw 'Unexpected daily task action; nothing changed' }
if (-not $Confirm) { Write-Output 'PLAN_ONLY=04:00 VIETNAM; task unchanged'; return }
$BackupRoot = Join-Path $ProjectRoot '.tmp-daily-task-backups'
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$Backup = Join-Path $BackupRoot ('reschedule-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.xml')
Export-ScheduledTask -TaskName $Task.TaskName | Set-Content -LiteralPath $Backup -Encoding UTF8
$Trigger = New-ScheduledTaskTrigger -Daily -At '04:00'
Set-ScheduledTask -TaskName $Task.TaskName -Trigger $Trigger | Out-Null
$Updated = Get-ScheduledTask -TaskName $Task.TaskName
if (@($Updated.Triggers).Count -ne 1 -or ([datetime]$Updated.Triggers[0].StartBoundary).TimeOfDay -ne [timespan]::FromHours(4)) {
    throw ('Schedule verification failed; restore XML backup: ' + $Backup)
}
Write-Output ('TASK_BACKUP=' + $Backup)
Write-Output 'DAILY_SCHEDULE=04:00 VIETNAM; actions/principal/settings/database unchanged; no task started or stopped'
$Updated | Get-ScheduledTaskInfo | Select-Object NextRunTime,LastRunTime,LastTaskResult
