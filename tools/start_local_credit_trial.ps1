param([int]$Port = 8770)
$ErrorActionPreference = 'Stop'
$trialRepository = Split-Path -Parent $PSScriptRoot
$trialSite = Join-Path $trialRepository '.tmp-credit-trial\site'
New-Item -ItemType Directory -Path $trialSite -Force | Out-Null
# Only UI assets; no .env, production data, Task Scheduler or Netlify calls.
foreach ($trialAsset in @('index.html','styles.css','bento.css','collection.css','admin.html','admin.css','formula-admin.css','local-trial.html','login-preview.html','vendor')) {
    Copy-Item -LiteralPath (Join-Path $trialRepository "web\$trialAsset") -Destination $trialSite -Recurse -Force
}
Push-Location $trialRepository
try {
    & (Join-Path $trialRepository 'node_modules\.bin\tsc.cmd') --outDir (Join-Path $trialSite 'dist')
    if ($LASTEXITCODE -ne 0) { throw 'Trial frontend build failed; no server started' }
    & (Join-Path $trialRepository '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'start_local_credit_trial.py') --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Local trial server did not finish successfully' }
}
finally { Pop-Location }
