param([switch]$ReplaceExisting)
$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
$Launcher = Join-Path $PSScriptRoot 'start_public_backend.py'
$StartScript = Join-Path $PSScriptRoot 'start_public_backend.ps1'
$TaskName = 'QD766 Public Backend'
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Set-Location -LiteralPath $RepositoryRoot
foreach ($path in @($Python, $Launcher, $StartScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Missing public backend files.' }
}
& $Python $Launcher --check
if ($LASTEXITCODE -ne 0) { throw 'Public configuration check failed. No task registered.' }
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    if (-not $ReplaceExisting) { throw 'Task already exists. Review it before using -ReplaceExisting.' }
    $BackupDirectory = Join-Path $RepositoryRoot '.tmp-public-task-backups'
    New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
    $BackupFile = Join-Path $BackupDirectory ('public-task-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.xml')
    Export-ScheduledTask -TaskName $TaskName | Set-Content -LiteralPath $BackupFile -Encoding UTF8
    Write-Output ('TASK_BACKUP=' + $BackupFile)
}
$Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $StartScript
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $Arguments -WorkingDirectory $RepositoryRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings
Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force | Out-Null
Write-Output 'PUBLIC_TASK_REGISTERED=QD766 Public Backend'
Write-Output 'TRIGGER=Current user logon; manual start also supported'
Write-Output 'Existing foreground server is NOT stopped; task is NOT started by this script.'
