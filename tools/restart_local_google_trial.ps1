param([switch]$GeminiAnalysis)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot 'start_local_google_trial.py'
$python = Join-Path $repo '.venv\Scripts\python.exe'
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
. (Join-Path $PSScriptRoot 'local_trial_process.ps1')
# Operate on the Google simulator only. Never public 8769, office 8767 or worker.
$listeners = @(Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction Stop)
$processIds = @($listeners.OwningProcess | Sort-Object -Unique)
if ($processIds.Count -ne 1) { throw 'Expected one verified local trial listener; nothing stopped.' }
$trialProcess = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $processIds[0])
if (-not $trialProcess) { throw 'Cannot read listener identity; nothing stopped.' }
$mode = @(Get-ReviewedLocalTrialMode -RepositoryRoot $repo -ExecutablePath $trialProcess.ExecutablePath -CommandLine $trialProcess.CommandLine)
if ($GeminiAnalysis) {
    if ($mode -notcontains '--source-wallet' -or $mode -contains '--expiry-rehearsal') {
        throw 'Gemini activation requires the standard isolated source-wallet trial; nothing stopped.'
    }
    if ($mode -notcontains '--gemini-analysis') { $mode += '--gemini-analysis' }
}
if (@($listeners | Where-Object { $_.LocalAddress -notin @('127.0.0.1','::1') }).Count -gt 0) {
    throw 'Trial is not loopback-only; nothing stopped.'
}
$currentPolicy=Invoke-RestMethod 'http://127.0.0.1:8771/api/v1/access-policy' -TimeoutSec 5
if ($currentPolicy.localGoogleTrial -ne $true) { throw 'Listener is not a local Google trial; nothing stopped.' }
& $python $launcher @mode --check
if ($LASTEXITCODE -ne 0) { throw 'Trial configuration invalid; nothing stopped.' }
$logs = Join-Path $repo '.tmp-credit-trial\logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
Stop-Process -Id $processIds[0] -ErrorAction Stop
for ($attempt=0; $attempt -lt 10; $attempt++) {
    if (-not (Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 300
}
if (Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue) { throw 'Trial port still occupied; no second server started.' }
$launchArgs = @('"' + $launcher + '"') + $mode
Start-Process -FilePath $pythonw -ArgumentList $launchArgs -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs 'group-export-restart.out.log') `
    -RedirectStandardError (Join-Path $logs 'group-export-restart.err.log') | Out-Null
for ($attempt=0; $attempt -lt 15; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $policy=Invoke-RestMethod 'http://127.0.0.1:8771/api/v1/access-policy' -TimeoutSec 2
        if ($policy.localGoogleTrial -eq $true -and $policy.groupExcelExportEnabled -eq $true -and $policy.collectionMonitorEnabled -eq $true -and ($mode -notcontains '--source-wallet' -or $policy.sharedRegistrationEnabled -eq $true) -and ($mode -notcontains '--gemini-analysis' -or $policy.geminiAnalysisEnabled -eq $true)) {
            Write-Output 'LOCAL_GOOGLE_TRIAL_READY=8771 GROUP_EXCEL_EXPORT=True COLLECTION_MONITOR=True PRODUCTION_UNCHANGED'
            if ($mode -contains '--gemini-analysis') {
                Write-Output 'GEMINI_ANALYSIS_ENABLED=True CREDIT=SIMULATED PROVIDER=REAL; API key/model access not verified until an explicit analysis request.'
            }
            exit 0
        }
    } catch { }
}
throw 'Trial did not become ready. Inspect .tmp-credit-trial/logs/group-export-restart.err.log locally.'
