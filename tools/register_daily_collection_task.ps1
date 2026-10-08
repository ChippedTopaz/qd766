param([string]$Backup, [switch]$Confirm, [PSCredential]$Credential, [switch]$AllowInteractive)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not $Confirm) {
    & $Python (Join-Path $PSScriptRoot 'run_daily_collection.py')
    Write-Output 'PLAN_ONLY: daily 05:00 Vietnam; old tasks/worker/database unchanged'
    return
}
if (-not $Backup) { throw 'Fresh verified database backup is required' }
if (-not $Credential -and -not $AllowInteractive) { throw 'Provide -Credential (Get-Credential) for logged-off execution, or explicitly choose -AllowInteractive' }
if ([TimeZoneInfo]::Local.BaseUtcOffset.TotalHours -ne 7) { throw 'Task host must use Vietnam UTC+07:00 timezone' }
$Tasks = @('QD766 National Summary','QD766 Province Detail Refresh','QD766 Worker')
$Worker = Get-ScheduledTask -TaskName 'QD766 Worker'
$OldActions = @($Worker.Actions)
if ($OldActions.Count -ne 1 -or $OldActions[0].Arguments -notmatch 'start_(?:controlled_)?worker\.ps1') { throw 'Unexpected worker action; nothing stopped' }
# Inspect exact known worker child processes before stopping anything.
$WorkerProcesses = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -in @('D:\QD766\app\.venv\Scripts\python.exe',$Python) -and
    $_.CommandLine -match 'run_collection_worker\.py(?:"|\s|$)'
})
& $Python (Join-Path $PSScriptRoot 'activate_daily_policy.py')
if ($LASTEXITCODE -ne 0) { throw 'Queue/control preflight failed; no task changes' }
$BackupRoot = Join-Path $ProjectRoot ('.tmp-daily-task-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
foreach ($Name in $Tasks) { Export-ScheduledTask -TaskName $Name | Set-Content -LiteralPath (Join-Path $BackupRoot ($Name+'.xml')) -Encoding UTF8 }
if (Get-ScheduledTask -TaskName 'QD766 Daily Collection' -ErrorAction SilentlyContinue) {
    Export-ScheduledTask -TaskName 'QD766 Daily Collection' | Set-Content -LiteralPath (Join-Path $BackupRoot 'QD766 Daily Collection.xml') -Encoding UTF8
}
& $Python (Join-Path $PSScriptRoot 'migrate_daily_history.py') --backup $Backup
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; schedules unchanged' }
foreach ($Name in $Tasks[0..1]) { Disable-ScheduledTask -TaskName $Name | Out-Null; Stop-ScheduledTask -TaskName $Name }
Stop-ScheduledTask -TaskName 'QD766 Worker'
foreach ($Process in $WorkerProcesses) {
    $Current = Get-CimInstance Win32_Process -Filter ('ProcessId = '+$Process.ProcessId)
    if ($Current -and $Current.ExecutablePath -eq $Process.ExecutablePath -and $Current.CommandLine -eq $Process.CommandLine) {
        Stop-Process -Id $Current.ProcessId -ErrorAction Stop
    } elseif ($Current) { throw 'Worker PID identity changed; collection remains paused' }
}
$WorkerAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $PSScriptRoot 'start_controlled_worker.ps1')) -WorkingDirectory $ProjectRoot
Set-ScheduledTask -TaskName 'QD766 Worker' -Action $WorkerAction | Out-Null
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $PSScriptRoot 'start_daily_collection.ps1')) -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At '05:00'
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15) -ExecutionTimeLimit (New-TimeSpan -Hours 2)
if ($Credential) {
    Register-ScheduledTask -TaskName 'QD766 Daily Collection' -Action $Action -Trigger $Trigger -Settings $Settings -User $Credential.UserName -Password $Credential.GetNetworkCredential().Password -Force | Out-Null
} else {
    $Principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'QD766 Daily Collection' -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
    Write-Warning 'Interactive mode: Windows account must remain logged in at 05:00'
}
& $Python (Join-Path $PSScriptRoot 'activate_daily_policy.py') --confirm
if ($LASTEXITCODE -ne 0) { throw 'Activation failed; keep collection paused and restore task XML if needed' }
Start-ScheduledTask -TaskName 'QD766 Worker'
Write-Output ('TASK_BACKUP='+$BackupRoot)
Write-Output 'DAILY_TASK_REGISTERED=05:00 VIETNAM; historical data retained; paid requests unchanged'
Write-Output 'Daily task NOT started now. Restart public backend using the reviewed restart script.'
