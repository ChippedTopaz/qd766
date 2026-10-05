$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local_trial_process.ps1')
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
$launcher = Join-Path $PSScriptRoot 'start_local_google_trial.py'
foreach ($script in @('tools\start_local_google_trial.py','.\tools\start_local_google_trial.py','tools/start_local_google_trial.py',$launcher)) {
    $mode = @(Get-ReviewedLocalTrialMode $repo $python ('"' + $python + '" "' + $script + '" --source-wallet'))
    if ($mode.Count -ne 1 -or $mode[0] -ne '--source-wallet') { throw 'Source wallet mode changed' }
    foreach ($tier in @('agency','province')) {
        $mode = @(Get-ReviewedLocalTrialMode $repo $python ('"' + $python + '" "' + $script + '" --source-wallet --expiry-rehearsal ' + $tier))
        if (($mode -join ' ') -ne ('--source-wallet --expiry-rehearsal ' + $tier)) { throw 'Rehearsal schema mode changed' }
    }
}
foreach ($script in @('tools\start_public_backend.py','tools\start_worker.py','C:\other\tools\start_local_google_trial.py')) {
    $rejected=$false
    try { Get-ReviewedLocalTrialMode $repo $python ('"' + $python + '" "' + $script + '"') | Out-Null } catch { $rejected=$true }
    if (-not $rejected) { throw 'Foreign launcher accepted' }
}
foreach ($flag in @('--seed-source-wallets','--prepare-expiry-rehearsal','--run-mock-worker-once','--bootstrap-owner','--expiry-rehearsal other')) {
    $rejected=$false
    try { Get-ReviewedLocalTrialMode $repo $python ('"' + $python + '" "' + $launcher + '" ' + $flag) | Out-Null } catch { $rejected=$true }
    if (-not $rejected) { throw 'Mutating/unrecognized startup flag accepted' }
}
$baseLine = Get-Content -LiteralPath (Join-Path $repo '.venv\pyvenv.cfg') | Where-Object { $_ -match '^executable\s*=' } | Select-Object -First 1
$basePython = ($baseLine -split '=',2)[1].Trim()
foreach ($script in @('.\tools\start_local_google_trial.py',$launcher)) {
    $mode = @(Get-ReviewedLocalTrialMode $repo $basePython ('"' + $python + '" "' + $script + '" --source-wallet'))
    if (($mode -join ' ') -ne '--source-wallet') { throw 'Windows venv redirector mode lost' }
}
$mode = @(Get-ReviewedLocalTrialMode $repo $basePython ('"' + $basePython + '" "' + $launcher + '" --source-wallet --expiry-rehearsal province'))
if (($mode -join ' ') -ne '--source-wallet --expiry-rehearsal province') { throw 'Absolute base interpreter launch failed' }
foreach ($foreignPython in @('C:\other\python.exe','C:\other\.venv\Scripts\python.exe')) {
    $rejected=$false
    try { Get-ReviewedLocalTrialMode $repo $foreignPython ('"' + $foreignPython + '" "' + $launcher + '"') | Out-Null } catch { $rejected=$true }
    if (-not $rejected) { throw 'Foreign Python accepted' }
}
Write-Output 'LOCAL_TRIAL_IDENTITY_TESTS=PASS INCLUDING_WINDOWS_VENV_REDIRECTOR NO_PROCESSES_STOPPED NO_DATABASE_CHANGES'
