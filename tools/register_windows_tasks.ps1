param(
    [string]$BackupDestination = "F:\QD766\backups",
    [string]$BackupTime = "01:30"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$BackendScript = Join-Path $PSScriptRoot "start_backend.ps1"
$BackupScript = Join-Path $PSScriptRoot "backup_postgresql.ps1"
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

foreach ($path in @($BackendScript, $BackupScript)) {
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
Write-Output "BACKUP_TASK=QD766 Backup (daily $BackupTime)"
Write-Output "BACKUP_DESTINATION=$BackupDestination"
