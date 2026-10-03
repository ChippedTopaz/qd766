param(
    [string]$DeploymentRoot = "D:\QD766\app",
    [string]$BackupDestination = "F:\QD766\backups",
    [string]$BackupTime = "01:30",
    [switch]$RegisterTasks
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent $PSScriptRoot
$SourceEnvironment = Join-Path $SourceRoot ".env"

if (-not (Test-Path -LiteralPath $SourceEnvironment)) {
    throw "Missing local configuration: $SourceEnvironment"
}

$resolvedSource = [IO.Path]::GetFullPath($SourceRoot).TrimEnd('\')
$resolvedTarget = [IO.Path]::GetFullPath($DeploymentRoot).TrimEnd('\')
if ($resolvedTarget -eq $resolvedSource -or $resolvedTarget.StartsWith($resolvedSource + '\')) {
    throw "DeploymentRoot must be outside the source repository"
}

New-Item -ItemType Directory -Force -Path $resolvedTarget | Out-Null

# Copy application sources without development/runtime state. Existing files are
# updated, but files that exist only in the deployment directory are not deleted.
& robocopy $resolvedSource $resolvedTarget /E /R:2 /W:1 `
    /XD ".git" ".venv" "node_modules" ".npm-cache" "__pycache__" ".tmp-*" "netlify-public" "tmp-pip" "tests\runtime-backend" "tests\runtime-collection" `
    /XF ".env" "*.pyc" "*.db" | Out-Null
$robocopyExitCode = $LASTEXITCODE
if ($robocopyExitCode -gt 7) {
    throw "Application copy failed with robocopy exit code $robocopyExitCode"
}

# The credential file stays local and is never included in Git.
$targetEnvironment = Join-Path $resolvedTarget ".env"
Copy-Item -LiteralPath $SourceEnvironment -Destination $targetEnvironment -Force

foreach ($line in Get-Content -LiteralPath $targetEnvironment) {
    $value = $line.Trim()
    if (-not $value -or $value.StartsWith("#")) {
        continue
    }
    $parts = $value.Split("=", 2)
    if ($parts.Count -eq 2) {
        Set-Item -Path ("Env:" + $parts[0]) -Value $parts[1]
    }
}
Remove-Item Env:QD766_DATABASE_URL -ErrorAction SilentlyContinue

$python = Join-Path $resolvedTarget ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    & py -3 -m venv (Join-Path $resolvedTarget ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the deployment Python environment"
    }
}

& $python -m pip install -e "$resolvedTarget[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install backend dependencies"
}

Push-Location $resolvedTarget
try {
    # Always capture a recoverable database image before applying a migration.
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $resolvedTarget "tools\backup_postgresql.ps1") `
        -Destination $BackupDestination
    if ($LASTEXITCODE -ne 0) {
        throw "Pre-migration PostgreSQL backup failed"
    }

    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed"
    }

    & $python tests\test_backend.py
    if ($LASTEXITCODE -ne 0) {
        throw "Backend verification failed"
    }

    if ($RegisterTasks) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
            (Join-Path $resolvedTarget "tools\register_windows_tasks.ps1") `
            -BackupDestination $BackupDestination `
            -BackupTime $BackupTime
        if ($LASTEXITCODE -ne 0) {
            throw "Windows task registration failed"
        }
    }
}
finally {
    Pop-Location
}

Write-Output "DEPLOYMENT_OK"
Write-Output "APPLICATION=$resolvedTarget"
Write-Output "BACKUP_DESTINATION=$BackupDestination"
Write-Output "TASKS_REGISTERED=$([bool]$RegisterTasks)"
