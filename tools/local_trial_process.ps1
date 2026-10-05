function Get-ReviewedLocalTrialMode {
    param([string]$RepositoryRoot, [string]$ExecutablePath, [string]$CommandLine)
    $expectedPython = @('python.exe','pythonw.exe') | ForEach-Object {
        [IO.Path]::GetFullPath((Join-Path $RepositoryRoot ('.venv\Scripts\' + $_)))
    }
    # Windows venv redirectors may have the configured base interpreter as the
    # listener executable. Derive that exact path from this project's pyvenv.cfg.
    $basePython = @()
    $configPath = Join-Path $RepositoryRoot '.venv\pyvenv.cfg'
    if (Test-Path -LiteralPath $configPath) {
        foreach ($line in Get-Content -LiteralPath $configPath) {
            if ($line -match '^executable\s*=\s*(.+)$') {
                $baseExecutable = [IO.Path]::GetFullPath($Matches[1].Trim())
                $basePython = @($baseExecutable, (Join-Path (Split-Path -Parent $baseExecutable) 'pythonw.exe'))
            }
        }
    }
    if (-not $ExecutablePath) { throw 'Cannot read listener executable path; try an Administrator PowerShell. Nothing stopped.' }
    $executable = [IO.Path]::GetFullPath($ExecutablePath)
    if ($executable -notin ($expectedPython + $basePython)) {
        throw 'Listener executable differs from project venv and its configured base Python; nothing stopped.'
    }
    $arguments = @([regex]::Matches($CommandLine, '"([^"]*)"|(\S+)') | ForEach-Object {
        if ($_.Groups[1].Success) { $_.Groups[1].Value } else { $_.Groups[2].Value }
    })
    if ($arguments.Count -lt 2) { throw 'Cannot identify local trial launcher; nothing stopped.' }
    $invokedPython = $arguments[0]
    if (-not [IO.Path]::IsPathRooted($invokedPython)) {
        $invokedPython = Join-Path $RepositoryRoot $invokedPython
    }
    $invokedPython = [IO.Path]::GetFullPath($invokedPython)
    if ($invokedPython -notin ($expectedPython + $basePython)) { throw 'Unreviewed interpreter invocation; nothing stopped.' }
    $script = $arguments[1].Replace('/', '\')
    $launcher = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot 'tools\start_local_google_trial.py'))
    if ([IO.Path]::IsPathRooted($script)) {
        $script = [IO.Path]::GetFullPath($script)
        if ($script -ne $launcher) { throw 'Listener uses a different launcher; nothing stopped.' }
    } elseif ($script -notin @('tools\start_local_google_trial.py','.\tools\start_local_google_trial.py')) {
        throw 'Unrecognized relative launcher; nothing stopped.'
    } elseif ($invokedPython -notin $expectedPython) {
        throw 'Base Python with a relative launcher needs identity inspection; nothing stopped.'
    }
    $mode = @()
    for ($index=2; $index -lt $arguments.Count; $index++) {
        switch ($arguments[$index]) {
            '--source-wallet' { if ($mode -contains '--source-wallet') { throw 'Duplicate mode; nothing stopped.' }; $mode += '--source-wallet' }
            '--expiry-rehearsal' {
                if ($mode -contains '--expiry-rehearsal' -or $index+1 -ge $arguments.Count -or
                    $arguments[$index+1] -notin @('agency','province')) { throw 'Invalid rehearsal mode; nothing stopped.' }
                $mode += @('--expiry-rehearsal',$arguments[++$index])
            }
            default { throw 'Unreviewed launch argument; nothing stopped.' }
        }
    }
    return $mode
}
