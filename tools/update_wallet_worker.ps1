# Run by the operator in administrator PowerShell. No environment or frontend deployment.
$ErrorActionPreference = 'Stop'
$SourceRoot = Split-Path -Parent $PSScriptRoot
$TargetRoot = 'D:\QD766\app'
$TargetPython = Join-Path $TargetRoot '.venv\Scripts\python.exe'
$SourcePython = Join-Path $SourceRoot '.venv\Scripts\python.exe'
$TaskName = 'QD766 Worker'
if (([IO.Path]::GetFullPath($TargetRoot)).TrimEnd('\') -ne 'D:\QD766\app') { throw 'Unexpected deployment target.' }
foreach ($file in @($TargetPython, (Join-Path $TargetRoot '.env'), (Join-Path $TargetRoot 'tools\start_worker.ps1'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'Deployment files missing; no worker stopped.' }
}
$Task = Get-ScheduledTask -TaskName $TaskName
$PublicTask = Get-ScheduledTask -TaskName 'QD766 Public Backend'
$PublicArguments = ($PublicTask.Actions | ForEach-Object { $_.Arguments }) -join ' '
if ($PublicTask.State -ne 'Running' -or $PublicArguments -notmatch '(?:^|\s)--real-wallet(?:\s|$)' -or
    $PublicArguments -notmatch '(?:^|\s)--pause-paid-requests(?:\s|$)') {
    throw 'Public real-wallet Task must be running with paid requests paused before worker update.'
}
$Actions = @($Task.Actions)
if ($Actions.Count -ne 1 -or $Actions[0].Arguments -notmatch [regex]::Escape((Join-Path $TargetRoot 'tools\start_worker.ps1')) -or
    $Actions[0].WorkingDirectory -ne $TargetRoot) { throw 'Worker Task differs from reviewed deployment.' }
& $SourcePython (Join-Path $PSScriptRoot 'check_credit_database_alignment.py') --office-file (Join-Path $TargetRoot '.env') --public-file (Join-Path $SourceRoot '.env.public')
if ($LASTEXITCODE -ne 0) { throw 'Database configurations differ; no worker stopped.' }
& $SourcePython (Join-Path $PSScriptRoot 'start_public_backend.py') --real-wallet --pause-paid-requests --check
if ($LASTEXITCODE -ne 0) { throw 'Wallet schema invalid; no worker stopped.' }
# Check the deployed interpreter dependencies before stopping a service.
# Windows PowerShell 5.1 strips embedded quotes in native -c arguments.
# Send static source through stdin so Python receives the code unchanged.
@'
import sqlalchemy, psycopg, alembic, httpx, fastapi
print("WORKER_DEPENDENCIES=PASS")
'@ | & $TargetPython -
if ($LASTEXITCODE -ne 0) { throw 'Worker dependencies missing; no worker stopped.' }
$BackupRoot = Join-Path $SourceRoot ('.tmp-worker-release\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $TargetRoot 'src\qd766') -Destination (Join-Path $BackupRoot 'qd766') -Recurse
Copy-Item -LiteralPath (Join-Path $TargetRoot 'tools\run_collection_worker.py') -Destination $BackupRoot
Export-ScheduledTask -TaskName $TaskName | Set-Content -LiteralPath (Join-Path $BackupRoot 'worker-task.xml') -Encoding UTF8
Write-Output ('WORKER_CODE_BACKUP=' + $BackupRoot)
Stop-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2
# Wrapper Task may leave a child. Match exact deployed Python and worker script only.
$Children = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -eq $TargetPython -and $_.CommandLine -match 'run_collection_worker\.py(?:"|\s|$)'
})
foreach ($Child in $Children) { Stop-Process -Id $Child.ProcessId }
Start-Sleep -Seconds 1
Copy-Item -LiteralPath (Join-Path $SourceRoot 'src\qd766') -Destination (Join-Path $TargetRoot 'src') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $SourceRoot 'tools\run_collection_worker.py') -Destination (Join-Path $TargetRoot 'tools\run_collection_worker.py') -Force
# Verify every copied source file before starting the new worker.
$SourcePackage = Join-Path $SourceRoot 'src\qd766'
foreach ($File in (Get-ChildItem -LiteralPath $SourcePackage -Recurse -File -Filter '*.py')) {
    $Relative = $File.FullName.Substring($SourcePackage.Length).TrimStart('\')
    $Deployed = Join-Path (Join-Path $TargetRoot 'src\qd766') $Relative
    if ((Get-FileHash -LiteralPath $File.FullName).Hash -ne (Get-FileHash -LiteralPath $Deployed).Hash) { throw 'Source verification failed; worker remains stopped.' }
}
Push-Location -LiteralPath $TargetRoot
try {
    @'
import sys
sys.path.insert(0,"src")
from qd766.backend.credit_wallet import finish
from qd766.backend.worker import run_one_job
print("WORKER_WALLET_IMPORTS=PASS")
'@ | & $TargetPython -
    if ($LASTEXITCODE -ne 0) { throw 'Updated worker imports failed; worker remains stopped.' }
} finally { Pop-Location }
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3
$UpdatedTask = Get-ScheduledTask -TaskName $TaskName
if ($UpdatedTask.State -ne 'Running') { throw 'Worker did not remain running. Inspect D:\QD766\logs\worker.log; keep public requests paused.' }
Write-Output 'WORKER_CODE_UPDATED=PASS'
Write-Output 'ENV_UNCHANGED FRONTEND_UNCHANGED PUBLIC_REQUESTS_MUST_REMAIN_PAUSED'
$UpdatedTask | Select-Object TaskName,State
