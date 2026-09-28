$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvironmentFile = Join-Path $RepositoryRoot ".env"
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing local configuration: $EnvironmentFile"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing Python environment: $Python"
}

foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
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

Set-Location -LiteralPath $RepositoryRoot
& $Python -m uvicorn qd766.backend.main:app --host 127.0.0.1 --port 8767
