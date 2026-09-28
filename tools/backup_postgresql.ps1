param(
    [string]$Destination = "F:\QD766\backups"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvironmentFile = Join-Path $RepositoryRoot ".env"
$PgDump = "G:\PostgreSQL\17\bin\pg_dump.exe"

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing local configuration: $EnvironmentFile"
}
if (-not (Test-Path -LiteralPath $PgDump)) {
    throw "pg_dump was not found at $PgDump"
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
    $value = $line.Trim()
    if (-not $value -or $value.StartsWith("#")) {
        continue
    }
    $parts = $value.Split("=", 2)
    if ($parts.Count -eq 2) {
        $settings[$parts[0]] = $parts[1]
    }
}

foreach ($name in @(
    "QD766_DATABASE_USER",
    "QD766_DATABASE_PASSWORD",
    "QD766_DATABASE_HOST",
    "QD766_DATABASE_PORT",
    "QD766_DATABASE_NAME"
)) {
    if (-not $settings.ContainsKey($name)) {
        throw "Missing $name in .env"
    }
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $Destination "qd766-$timestamp.dump"
$hashFile = "$backupFile.sha256"

$env:PGPASSWORD = $settings["QD766_DATABASE_PASSWORD"]
try {
    & $PgDump `
        --host=$($settings["QD766_DATABASE_HOST"]) `
        --port=$($settings["QD766_DATABASE_PORT"]) `
        --username=$($settings["QD766_DATABASE_USER"]) `
        --dbname=$($settings["QD766_DATABASE_NAME"]) `
        --format=custom `
        --compress=9 `
        --no-password `
        --file=$backupFile
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $backupFile) -or (Get-Item $backupFile).Length -eq 0) {
    throw "Backup file is missing or empty"
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $backupFile
Set-Content -LiteralPath $hashFile -Value "$($hash.Hash)  $([IO.Path]::GetFileName($backupFile))" -Encoding ascii

Write-Output "BACKUP_OK"
Write-Output "FILE=$backupFile"
Write-Output "SIZE_BYTES=$((Get-Item $backupFile).Length)"
Write-Output "SHA256=$($hash.Hash)"
