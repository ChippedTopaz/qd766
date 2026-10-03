$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
$Launcher = Join-Path $PSScriptRoot 'start_public_backend.py'
$LogDirectory = Join-Path $RepositoryRoot '.tmp-public-logs'
$LogFile = Join-Path $LogDirectory 'public-backend.log'
foreach ($path in @($Python, $Launcher, (Join-Path $RepositoryRoot '.env.public'))) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Missing public backend runtime/configuration.' }
}
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
if ((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length -gt 10MB) {
    $ArchivedLog = Join-Path $LogDirectory ('public-backend-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.log')
    Move-Item -LiteralPath $LogFile -Destination $ArchivedLog
}
Set-Location -LiteralPath $RepositoryRoot
Add-Content -LiteralPath $LogFile -Value ('RUN_STARTED=' + (Get-Date -Format o))
# Native stderr INFO output must not terminate a healthy Uvicorn process.
$ErrorActionPreference = 'Continue'
& $Python $Launcher *>> $LogFile
$PublicExitCode = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
Add-Content -LiteralPath $LogFile -Value ('RUN_FINISHED=' + (Get-Date -Format o) + ' EXIT_CODE=' + $PublicExitCode)
exit $PublicExitCode
