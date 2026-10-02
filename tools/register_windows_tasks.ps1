param(
    [string]$BackupDestination = "F:\QD766\backups",
    [string]$BackupTime = "01:30"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$BackendScript = Join-Path $PSScriptRoot "start_backend.ps1"
$WorkerScript = Join-Path $PSScriptRoot "start_worker.ps1"
$NationalSummaryScript = Join-Path $PSScriptRoot "start_national_summary.ps1"
$ProvinceRefreshScript = Join-Path $PSScriptRoot "start_province_refresh.ps1"
$BackupScript = Join-Path $PSScriptRoot "backup_postgresql.ps1"
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

foreach ($path in @($BackendScript, $WorkerScript, $NationalSummaryScript, $ProvinceRefreshScript, $BackupScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing required script: $path"
    }
}

New-Item -ItemType Directory -Force -Path $BackupDestination | Out-Null

$principal = New-ScheduledTaskPrincipal `
    -UserId $CurrentUser `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$backendArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $BackendScript
$backendAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $backendArguments `
    -WorkingDirectory $RepositoryRoot
$backendTrigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
$backendTask = New-ScheduledTask `
    -Action $backendAction `
    -Trigger $backendTrigger `
    -Principal $principal `
    -Settings $settings
Register-ScheduledTask -TaskName "QD766 Backend" -InputObject $backendTask -Force | Out-Null

$workerArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $WorkerScript
$workerAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $workerArguments `
    -WorkingDirectory $RepositoryRoot
$workerTrigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
$workerTask = New-ScheduledTask `
    -Action $workerAction `
    -Trigger $workerTrigger `
    -Principal $principal `
    -Settings $settings
Register-ScheduledTask -TaskName "QD766 Worker" -InputObject $workerTask -Force | Out-Null

$nationalSummaryArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $NationalSummaryScript
$nationalSummaryAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $nationalSummaryArguments `
    -WorkingDirectory $RepositoryRoot
$nationalSummaryTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At ((Get-Date).AddMinutes(5)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$nationalSummaryTask = New-ScheduledTask `
    -Action $nationalSummaryAction `
    -Trigger $nationalSummaryTrigger `
    -Principal $principal `
    -Settings $settings
Register-ScheduledTask -TaskName "QD766 National Summary" -InputObject $nationalSummaryTask -Force | Out-Null

$provinceRefreshArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $ProvinceRefreshScript
$provinceRefreshAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $provinceRefreshArguments `
    -WorkingDirectory $RepositoryRoot
$provinceRefreshTrigger = New-ScheduledTaskTrigger -Daily -At "02:15"
$provinceRefreshTask = New-ScheduledTask `
    -Action $provinceRefreshAction `
    -Trigger $provinceRefreshTrigger `
    -Principal $principal `
    -Settings $settings
Register-ScheduledTask -TaskName "QD766 Province Detail Refresh" -InputObject $provinceRefreshTask -Force | Out-Null

$backupArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Destination "{1}"' -f $BackupScript, $BackupDestination
$backupAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $backupArguments `
    -WorkingDirectory $RepositoryRoot
$backupTrigger = New-ScheduledTaskTrigger -Daily -At $BackupTime
$backupTask = New-ScheduledTask `
    -Action $backupAction `
    -Trigger $backupTrigger `
    -Principal $principal `
    -Settings $settings
Register-ScheduledTask -TaskName "QD766 Backup" -InputObject $backupTask -Force | Out-Null

Write-Output "TASKS_REGISTERED"
Write-Output "BACKEND_TASK=QD766 Backend (at logon)"
Write-Output "WORKER_TASK=QD766 Worker (at logon; circuit-protected)"
Write-Output "NATIONAL_SUMMARY_TASK=QD766 National Summary (hourly; circuit-protected)"
Write-Output "PROVINCE_REFRESH_TASK=QD766 Province Detail Refresh (daily 02:15; staggered 72h; circuit-protected)"
Write-Output "BACKUP_TASK=QD766 Backup (daily $BackupTime)"
Write-Output "BACKUP_DESTINATION=$BackupDestination"
