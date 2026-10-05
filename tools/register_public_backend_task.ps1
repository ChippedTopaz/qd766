param([switch]$ReplaceExisting, [switch]$RealWallet, [switch]$PausePaidRequests, [switch]$SharedRegistration)
$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
$Launcher = Join-Path $PSScriptRoot 'start_public_backend.py'
$BackgroundPython = Join-Path $RepositoryRoot '.venv\Scripts\pythonw.exe'
$TaskName = 'QD766 Public Backend'
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Set-Location -LiteralPath $RepositoryRoot
foreach ($path in @($Python, $Launcher, $BackgroundPython)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Missing public backend files.' }
}
if ($PausePaidRequests -and -not $RealWallet) { throw 'Pause requires -RealWallet.' }
if ($SharedRegistration -and -not $RealWallet) { throw 'Shared registration requires -RealWallet.' }
$ModeArguments = @()
if ($RealWallet) { $ModeArguments += '--real-wallet' }
if ($PausePaidRequests) { $ModeArguments += '--pause-paid-requests' }
if ($SharedRegistration) { $ModeArguments += '--shared-registration' }
& $Python $Launcher @ModeArguments --check
if ($LASTEXITCODE -ne 0) { throw 'Public configuration check failed. No task registered.' }
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    if (-not $SharedRegistration -and (($ExistingTask.Actions | ForEach-Object { $_.Arguments }) -join ' ') -match '--shared-registration') {
        throw 'Cannot silently disable shared registration. Preserve -SharedRegistration when replacing this task.'
    }
    if (-not $RealWallet -and (($ExistingTask.Actions | ForEach-Object { $_.Arguments }) -join ' ') -match '--real-wallet') {
        throw 'Cannot replace a real-wallet task with legacy mode. Use -RealWallet; pause if necessary.'
    }
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
# Direct windowless Python action: no PowerShell wrapper to leave a child server behind.
$Arguments = '"{0}" --background-log' -f $Launcher
if ($ModeArguments.Count) { $Arguments += ' ' + ($ModeArguments -join ' ') }
$Action = New-ScheduledTaskAction -Execute $BackgroundPython -Argument $Arguments -WorkingDirectory $RepositoryRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings
Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force | Out-Null
Write-Output 'PUBLIC_TASK_REGISTERED=QD766 Public Backend'
Write-Output 'TRIGGER=Current user logon; manual start also supported'
Write-Output 'Existing foreground server is NOT stopped; task is NOT started by this script.'
