param([switch]$Confirm, [PSCredential]$Credential)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Script = Join-Path $PSScriptRoot 'start_source_monitor.ps1'
$TaskName = 'QD766 Source Monitor'
if (-not $Confirm) { & $Python (Join-Path $PSScriptRoot 'run_source_monitor.py'); return }
if ([TimeZoneInfo]::Local.BaseUtcOffset.TotalHours -ne 7) { throw 'Host must use Vietnam UTC+07:00 timezone' }
$Daily = Get-ScheduledTask -TaskName 'QD766 Daily Collection'
if (@($Daily.Actions).Count -ne 1 -or $Daily.Actions[0].WorkingDirectory -ne $ProjectRoot -or
    -not $Daily.Actions[0].Arguments.Contains((Join-Path $PSScriptRoot 'start_daily_collection.ps1'))) { throw 'Unexpected daily task; nothing changed' }
if ($Daily.Principal.LogonType -eq 'Password' -and -not $Credential) { throw 'Daily task runs logged-off. Supply -Credential (Get-Credential) to register this separate task; never downgrade to interactive silently.' }
if ($Credential -and $Credential.UserName -ne $Daily.Principal.UserId) { throw 'Credential must match the daily task principal' }
& $Python (Join-Path $PSScriptRoot 'run_source_monitor.py') --check
if ($LASTEXITCODE -ne 0) { throw 'Schema check failed; no task changes' }
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing -and (@($Existing.Actions).Count -ne 1 -or -not $Existing.Actions[0].Arguments.Contains($Script))) { throw 'Existing task is not the managed monitor; no overwrite' }
$BackupRoot = Join-Path $ProjectRoot ('.tmp-source-monitor-task-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
Export-ScheduledTask -TaskName $Daily.TaskName | Set-Content -LiteralPath (Join-Path $BackupRoot 'daily-unchanged.xml') -Encoding UTF8
if ($Existing) { Export-ScheduledTask -TaskName $TaskName | Set-Content -LiteralPath (Join-Path $BackupRoot 'monitor-before.xml') -Encoding UTF8 }
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $Script) -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At '06:00'
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 4)
if ($Credential) { Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -User $Credential.UserName -Password $Credential.GetNetworkCredential().Password -Force | Out-Null }
else { Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Daily.Principal -Force | Out-Null }
$Updated = Get-ScheduledTask -TaskName $TaskName
if (@($Updated.Triggers).Count -ne 1 -or ([datetime]$Updated.Triggers[0].StartBoundary).TimeOfDay -ne [timespan]::FromHours(6)) { throw 'Monitor schedule verification failed; inspect saved XML' }
Write-Output ('TASK_BACKUP=' + $BackupRoot)
Write-Output 'SOURCE_MONITOR_SCHEDULE=06:00 VIETNAM; task not started now; daily task/worker unchanged'
$Updated | Get-ScheduledTaskInfo | Select-Object NextRunTime,LastRunTime,LastTaskResult
